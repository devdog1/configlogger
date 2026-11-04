import logging

logger = logging.getLogger("oxidized.hook")

class Hook:
    def __init__(self, cfg=None):
        self.cfg = cfg or {}

    def run_hook(self, ctx):
        pass


class ExecHook(Hook):
    def run_hook(self, ctx):
        cmd = self.cfg.get('cmd')
        if not cmd:
            return
        import subprocess
        try:
            subprocess.run(cmd, shell=True, check=False)
        except Exception as e:
            logger.error("ExecHook failed: %s", e)


class HookManager:
    def __init__(self, hooks=None):
        self.hooks = hooks or []

    @classmethod
    def from_config(cls, cfg):
        hooks = []
        raw_hooks = cfg.get('hooks', {}) if cfg else {}
        for name, hook_cfg in raw_hooks.items():
            hook_type = hook_cfg.get('type')
            if hook_type == 'exec':
                hooks.append(ExecHook(hook_cfg))
        return cls(hooks)

    def handle(self, event, node=None, status=None):
        for h in self.hooks:
            try:
                h.run_hook({'event': event, 'node': node, 'status': status})
            except Exception as e:
                logger.error("Error running hook: %s", e)
