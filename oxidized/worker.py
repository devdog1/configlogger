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
        existing_names = {n.name for n in self.queue}
        for n in self.nodes:
            if n.name not in existing_names:
                self.queue.append(n)

    def next(self, node_name):
        node = self.nodes.get(node_name)
        if node:
            if node in self.queue:
                self.queue.remove(node)
            self.head_queue.insert(0, node)
            return True
        return False

    def work(self):
        if not self.head_queue and not self.queue:
            return

        node = self.head_queue.pop(0) if self.head_queue else self.queue.pop(0)
        if node.running:
            self.queue.append(node)
            return

        def task(n):
            logger.info("Worker starting node %s", n.name)
            self.hooks.handle('node_start', node=n)
            success = n.run()
            status = 'success' if success else 'fail'
            self.hooks.handle('node_end', node=n, status=status)
            logger.info("Worker finished node %s (status: %s)", n.name, status)
            self.queue.append(n)

        self.pool.submit(task, node)
