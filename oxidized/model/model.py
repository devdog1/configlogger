import re
import datetime
from collections import defaultdict

class ModelOutputs(list):
    """Container for outputs of commands run during model extraction."""
    def to_cfg(self):
        return "\n".join(str(item) for item in self if item)


class ModelMeta(type):
    """Metaclass to handle Model inheritance and command/callback registry."""
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        cls._cmds = {'cmd': [], 'all': [], 'secret': [], 'significant_changes': []}
        cls._procs = {'pre': [], 'post': []}
        cls._expects = []
        cls._cfgs = defaultdict(list)
        cls._prompt = None
        cls._comment = "! "
        cls._inputs = None
        cls._metadata = {}

        # Inherit definitions from base classes
        for base in reversed(bases):
            if hasattr(base, '_cmds'):
                for k, v in base._cmds.items():
                    cls._cmds[k].extend(list(v))
            if hasattr(base, '_procs'):
                for k, v in base._procs.items():
                    cls._procs[k].extend(list(v))
            if hasattr(base, '_expects'):
                cls._expects.extend(list(base._expects))
            if hasattr(base, '_comment') and base._comment:
                cls._comment = base._comment
            if hasattr(base, '_prompt') and base._prompt:
                cls._prompt = base._prompt
        return cls


class Model(metaclass=ModelMeta):
    METADATA_DEFAULT = "{comment}Fetched by Oxidized with model {model} from host {name} [{ip}]\n"

    def __init__(self, node=None):
        self.node = node
        self.input = None

    @classmethod
    def prompt(cls, regex=None):
        if regex is not None:
            cls._prompt = regex
        return cls._prompt

    @classmethod
    def comment(cls, text=None):
        if text is not None:
            cls._comment = text
        return cls._comment

    @classmethod
    def expect(cls, regex, callback=None):
        cls._expects.append((re.compile(regex) if isinstance(regex, str) else regex, callback))

    @classmethod
    def cmd(cls, cmd_arg, **kwargs):
        """Decorator or function to register a command or filter."""
        def decorator(func):
            if cmd_arg in (':all', 'all'):
                cls._cmds['all'].append(func)
            elif cmd_arg in (':secret', 'secret'):
                cls._cmds['secret'].append(func)
            elif cmd_arg in (':significant_changes', 'significant_changes'):
                cls._cmds['significant_changes'].append(func)
            else:
                cls._cmds['cmd'].append({'cmd': cmd_arg, 'args': kwargs, 'func': func})
            return func

        if kwargs.get('func'):
            func = kwargs.pop('func')
            return decorator(func)
        if callable(cmd_arg) and not kwargs:
            return decorator(cmd_arg)
        return decorator

    @classmethod
    def add_cmd(cls, cmd_string, func=None, **kwargs):
        cls._cmds['cmd'].append({'cmd': cmd_string, 'args': kwargs, 'func': func})

    @classmethod
    def add_all(cls, func):
        cls._cmds['all'].append(func)

    @classmethod
    def add_secret(cls, func):
        cls._cmds['secret'].append(func)

    @classmethod
    def pre(cls, func):
        cls._procs['pre'].append(func)
        return func

    @classmethod
    def post(cls, func):
        cls._procs['post'].append(func)
        return func

    @classmethod
    def cfg(cls, *methods):
        def decorator(func):
            for method in methods:
                cls._cfgs[str(method)].append(func)
            return func
        return decorator

    def execute_cmd(self, string, input_filter=None, func=None):
        if input_filter:
            input_name = getattr(self.input, 'name', '').lower()
            allowed = [input_filter] if isinstance(input_filter, str) else input_filter
            if input_name not in [a.lower() for a in allowed]:
                return ''

        if self.input:
            out = self.input.cmd(string)
        else:
            out = f"Mock output for {string}"

        if out is False or out is None:
            return False

        # Apply :all filters
        for f in self._cmds['all']:
            out = f(self, out, string) if f.__code__.co_argcount >= 3 else f(self, out)

        # Apply :secret filters if remove_secret is True
        if self.vars('remove_secret'):
            for f in self._cmds['secret']:
                out = f(self, out, string) if f.__code__.co_argcount >= 3 else f(self, out)

        # Apply command-specific block
        if func:
            out = func(self, out)

        return out

    def get(self):
        """Execute all commands and assemble outputs."""
        outputs = ModelOutputs()
        for cmd_entry in self._cmds['cmd']:
            command = cmd_entry['cmd']
            args = cmd_entry.get('args', {})
            func = cmd_entry.get('func')

            if 'if' in args and callable(args['if']) and not args['if'](self):
                continue

            out = self.execute_cmd(command, input_filter=args.get('input'), func=func)
            if out is False:
                return False
            if out:
                outputs.append(out)

        # Run pre procs
        for pre_proc in self._procs['pre']:
            pre_out = pre_proc(self)
            if pre_out:
                outputs.insert(0, pre_out)

        # Run post procs
        for post_proc in self._procs['post']:
            post_out = post_proc(self)
            if post_out:
                outputs.append(post_out)

        if self.vars('metadata') is True:
            meta_top = self.metadata('top')
            meta_bot = self.metadata('bottom')
            if meta_top:
                outputs.insert(0, meta_top)
            if meta_bot:
                outputs.append(meta_bot)

        return outputs

    def vars(self, key):
        if self.node and self.node.vars:
            return self.node.vars.get(key)
        return None

    def metadata(self, position):
        if position == 'top':
            name = self.node.name if self.node else "unknown"
            ip = self.node.ip if self.node else "unknown"
            group = self.node.group if self.node else ""
            model_name = self.__class__.__name__
            comment = self._comment or "! "
            return self.METADATA_DEFAULT.format(
                comment=comment,
                model=model_name,
                name=name,
                ip=ip,
                group=group
            )
        return None

    @classmethod
    def clean_cut(cls, head=1, tail=1):
        def _cut(model, out, cmd=""):
            lines = out.splitlines()
            if len(lines) > head + tail:
                return "\n".join(lines[head:-tail])
            return out
        cls.add_all(_cut)
