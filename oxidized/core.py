import os
import time
import logging
import signal
import sys
from pathlib import Path
from oxidized.config import Config
from oxidized.nodes import Nodes
from oxidized.worker import Worker
from oxidized.hook import HookManager
from oxidized.exceptions import NoNodesFound

logger = logging.getLogger("oxidized.core")

class Core:
    _instance = None

    def __init__(self, opts=None):
        Core._instance = self
        self.opts = opts or {}
        self.cfg = Config.load(self.opts)
        self.hooks = HookManager.from_config(self.cfg)
        self.nodes = Nodes()
        self.worker = Worker(self.nodes)
        self.need_reload = False
        self._running = False
        self.pid_file = self._resolve_pid_file()

        self._setup_signals()

    @classmethod
    def current(cls):
        return cls._instance

    def _resolve_pid_file(self):
        pid_path = getattr(self.cfg, 'pid', None) or os.path.join(Config.ROOT, 'pid')
        return os.path.expanduser(str(pid_path))

    def _write_pid_file(self):
        try:
            if self.pid_file:
                os.makedirs(os.path.dirname(self.pid_file), exist_ok=True)
                with open(self.pid_file, 'w', encoding='utf-8') as f:
                    f.write(str(os.getpid()))
                logger.info("Wrote daemon PID %s to %s", os.getpid(), self.pid_file)
        except Exception as e:
            logger.warning("Could not write PID file %s: %s", self.pid_file, e)

    def _remove_pid_file(self):
        try:
            if self.pid_file and os.path.exists(self.pid_file):
                # Only remove if it contains our PID
                with open(self.pid_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                if content == str(os.getpid()):
                    os.remove(self.pid_file)
                    logger.info("Removed PID file %s", self.pid_file)
        except Exception as e:
            logger.debug("Could not remove PID file %s: %s", self.pid_file, e)

    def _setup_signals(self):
        try:
            signal.signal(signal.SIGHUP, self._handle_sighup)
        except Exception:
            pass
        try:
            signal.signal(signal.SIGTERM, self._handle_sigterm)
        except Exception:
            pass

    def _handle_sighup(self, signum, frame):
        logger.info("Received SIGHUP, scheduling node & config reload")
        self.need_reload = True

    def _handle_sigterm(self, signum, frame):
        logger.info("Received SIGTERM, stopping Oxidized daemon...")
        self.stop()
        sys.exit(0)

    def reload(self):
        """Reload configuration settings from PostgreSQL and refresh node inventory."""
        logger.info("Reloading configuration and nodes...")
        try:
            self.cfg = Config.load(self.opts)
            self.worker.cfg = self.cfg
            self.worker.threads_count = int(self.cfg.threads or 30)
        except Exception as e:
            logger.error("Error refreshing configuration on reload: %s", e)
        self.worker.reload()
        self.need_reload = False
        logger.info("Reload completed. Currently managing %d nodes.", len(self.worker.queue))

    def run(self):
        logger.info("Starting Oxidized worker loop (PID: %s)...", os.getpid())
        self._write_pid_file()
        self._running = True
        try:
            while self._running:
                if self.need_reload:
                    self.reload()
                self.worker.work()
                if self.cfg.run_once:
                    break
                time.sleep(Config.SLEEP)
        except KeyboardInterrupt:
            logger.info("Oxidized interrupted, stopping.")
        finally:
            self.stop()

    def stop(self):
        self._running = False
        self._remove_pid_file()
        if hasattr(self.worker, 'pool'):
            self.worker.pool.shutdown(wait=False)
        if Core._instance is self:
            Core._instance = None
