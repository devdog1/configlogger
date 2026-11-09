import time
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from oxidized.config import Config
from oxidized.hook import HookManager

logger = logging.getLogger("oxidized.worker")

class Job:
    def __init__(self, node):
        self.node = node
        self.start = None
        self.end = None
        self.status = None


class Worker:
    def __init__(self, nodes):
        self.nodes = nodes
        self.cfg = Config.current()
        self.threads_count = int(self.cfg.threads or 30)
        self.pool = ThreadPoolExecutor(max_workers=self.threads_count)
        self.queue = list(self.nodes)
        self.head_queue = []
        self.hooks = HookManager.from_config(self.cfg)
        self.running = True

    def reload(self):
        logger.info("Reloading worker nodes")
        self.nodes.load()
        existing_map = {n.name: n for n in self.queue}
        new_queue = []
        for n in self.nodes:
            if n.name in existing_map:
                old_node = existing_map[n.name]
                # Preserve runtime execution state if available
                n.last = old_node.last
                n.attempts = old_node.attempts
                n.last_error = old_node.last_error
                n.running = old_node.running
                n.last_attempt = old_node.last_attempt
                n.last_modified = old_node.last_modified
            new_queue.append(n)
        self.queue = new_queue

    def next(self, node_name):
        node = self.nodes.get(node_name)
        if node:
            node.nexted = True
            if node in self.queue:
                self.queue.remove(node)
            if node not in self.head_queue:
                self.head_queue.insert(0, node)
            return True
        return False

    def work(self):
        if not self.head_queue and not self.queue:
            return

        # Head queue items have priority (e.g. manual trigger or explicitly nexted)
        if self.head_queue:
            node = self.head_queue.pop(0)
            if node.running:
                self.head_queue.append(node)
                return
            node.nexted = False
            self._dispatch_node(node)
            return

        # Regular auto check queue: check node readiness respecting interval and timeout
        timeout = int(getattr(self.cfg, 'timeout', 20) or 20)

        # Inspect nodes in the queue to find one ready for checking
        ready_node = None
        checked_count = 0
        total_in_queue = len(self.queue)

        while checked_count < total_in_queue:
            candidate = self.queue.pop(0)
            checked_count += 1

            if candidate.running:
                self.queue.append(candidate)
                continue

            node_timeout = int(getattr(candidate, 'timeout', timeout) or timeout)
            # is_ready_for_check automatically uses candidate.effective_interval() and candidate.timeout
            if candidate.is_ready_for_check(fail_timeout=node_timeout):
                ready_node = candidate
                break
            else:
                # Not yet ready (waiting interval after success, or timeout after failure)
                self.queue.append(candidate)

        if ready_node:
            self._dispatch_node(ready_node)

    def _dispatch_node(self, node):
        def task(n):
            logger.info("Worker starting node %s", n.name)
            self.hooks.handle('node_start', node=n)
            success = n.run()
            status = 'success' if success else 'fail'
            self.hooks.handle('node_end', node=n, status=status)
            logger.info("Worker finished node %s (status: %s)", n.name, status)
            self.queue.append(n)

        self.pool.submit(task, node)
