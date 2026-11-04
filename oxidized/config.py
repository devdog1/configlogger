import os
import copy
import yaml
from pathlib import Path
from oxidized.exceptions import NoConfig, InvalidConfig

class ConfigDict(dict):
    """Dictionary supporting dot and attribute notation, similar to Ruby's Asetus."""
    def __init__(self, *args, **kwargs):
        super().__init__()
        for arg in args:
            if isinstance(arg, dict):
                for k, v in arg.items():
                    self[k] = v
        for k, v in kwargs.items():
            self[k] = v

    def __getattr__(self, name):
        if name.endswith('?'):
            key = name[:-1]
            return bool(self.get(key, False))
        if name in self:
            return self[name]
        return None

    def __setattr__(self, name, value):
        self[name] = value

    def __getitem__(self, key):
        return super().get(key, None)

    def __setitem__(self, key, value):
        if isinstance(value, dict) and not isinstance(value, ConfigDict):
            value = ConfigDict(value)
        super().__setitem__(key, value)

    def get_path(self, path, default=None):
        parts = path.split('.')
        curr = self
        for part in parts:
            if isinstance(curr, dict) and part in curr:
                curr = curr[part]
            else:
                return default
        return curr


class Config:
    ROOT = os.environ.get('OXIDIZED_HOME', str(Path.home() / '.config' / 'oxidized'))
    CRASH = os.environ.get('OXIDIZED_LOGS', os.path.join(ROOT, 'crash'))
    LOG = os.environ.get('OXIDIZED_LOGS', os.path.join(ROOT, 'logs'))
    SLEEP = 1

    _config = None

    @classmethod
    def get_defaults(cls):
        defaults = {
            'username': 'username',
            'password': 'password',
            'model': 'junos',
            'resolve_dns': True,
            'interval': 3600,
            'debug': False,
            'run_once': False,
            'threads': 30,
            'use_max_threads': False,
            'timeout': 20,
            'timelimit': 300,
            'retries': 3,
            'prompt': r'^([\w.@-]+[#>]\s?)$',
            'next_adds_job': False,
            'vars': {},
            'groups': {},
            'group_map': {},
            'models': {},
            'pid': os.path.join(cls.ROOT, 'pid'),
            'extensions': {
                'oxidized-web': {
                    'load': False,
                    'listen': '127.0.0.1:8888',
                }
            },
            'crash': {
                'directory': os.path.join(cls.ROOT, 'crashes'),
                'hostnames': False
            },
            'stats': {
                'history_size': 10
            },
            'input': {
                'default': 'ssh, telnet',
                'debug': False,
                'ssh': {
                    'secure': False
                },
                'ftp': {
                    'passive': True
                },
                'utf8_encoded': True
            },
            'output': {
                'default': 'file',
                'file': {
                    'directory': os.path.join(cls.ROOT, 'configs')
                },
                'git': {
                    'user': 'Oxidized',
                    'email': 'o@example.com',
                    'repo': os.path.join(cls.ROOT, 'oxidized.git'),
                    'single_repo': True
                }
            },
            'source': {
                'default': 'csv',
                'csv': {
                    'file': os.path.join(cls.ROOT, 'router.db'),
                    'delimiter': ':',
                    'map': {
                        'name': 0,
                        'model': 1,
                    },
                    'vars_map': {},
                    'gpg': False
                },
                'django': {
                    'app': 'oxidized_web'
                }
            },
            'model_map': {
                'juniper': 'junos',
                'cisco': 'ios'
            },
            'hooks': {}
        }
        return ConfigDict(defaults)

    @classmethod
    def load(cls, cmd_opts=None):
        cmd_opts = cmd_opts or {}
        cfg = cls.get_defaults()

        # Check if Django model configuration exists first
        loaded_from_db = False
        try:
            import django
            if os.environ.get('DJANGO_SETTINGS_MODULE'):
                django.setup()
                from oxidized_web.models import OxidizedSetting
                db_cfg = OxidizedSetting.get_config_dict()
                if db_cfg and isinstance(db_cfg, dict):
                    cls._deep_merge(cfg, db_cfg)
                    loaded_from_db = True
        except Exception:
            pass

        if not loaded_from_db:
            usrdir = os.path.expanduser(cmd_opts.get('home_dir') or cls.ROOT)
            cfgfile = cmd_opts.get('config_file') or 'config'
            full_path = os.path.join(usrdir, cfgfile)
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f:
                    file_cfg = yaml.safe_load(f.read())
                    if isinstance(file_cfg, dict):
                        cls._deep_merge(cfg, file_cfg)

        if cmd_opts.get('debug') is not None:
            cfg.debug = cmd_opts['debug']

        cls._config = cfg
        return cfg

    @classmethod
    def _deep_merge(cls, base, update):
        for k, v in update.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                cls._deep_merge(base[k], v)
            else:
                base[k] = v

    @classmethod
    def current(cls):
        if cls._config is None:
            cls.load()
        return cls._config
