import time
import logging
import signal
import sys
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

        self._setup_signals()

    @classmethod
    def current(cls):
        return cls._instance

    def _setup_signals(self):
        try:
            signal.signal(signal.SIGHUP, self._handle_sighup)
        except Exception:
            pass

    def _handle_sighup(self, signum, frame):
        logger.info("Received SIGHUP, scheduling node reload")
        self.need_reload = True

    def reload(self):
        logger.info("Reloading nodes...")
        self.worker.reload()
        self.need_reload = False

    def run(self):
        logger.info("Starting Oxidized worker loop...")
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
        if hasattr(self.worker, 'pool'):
            self.worker.pool.shutdown(wait=False)
