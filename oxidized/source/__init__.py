import os
import re
import logging
from oxidized.exceptions import InvalidConfig

logger = logging.getLogger("oxidized.source")

class Source:
    def __init__(self, cfg=None):
        self.cfg = cfg or {}

    def setup(self):
        pass

    def load(self, node_want=None):
        raise NotImplementedError


class CSVSource(Source):
    def __init__(self, cfg=None):
        super().__init__(cfg)
        self.file_path = os.path.expanduser(self.cfg.get('file', '~/.config/oxidized/router.db'))
        self.delimiter = self.cfg.get('delimiter', ':')
        self.map = self.cfg.get('map', {'name': 0, 'model': 1})
        self.vars_map = self.cfg.get('vars_map', {})

    def load(self, node_want=None):
        nodes = []
        if not os.path.exists(self.file_path):
            return nodes

        with open(self.file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in re.split(self.delimiter, line)]
            node = {}
            for k, pos in self.map.items():
                if int(pos) < len(parts):
                    node[k] = parts[int(pos)]
            node_vars = {}
            for k, pos in self.vars_map.items():
                if int(pos) < len(parts):
                    node_vars[k] = parts[int(pos)]
            if node_vars:
                node['vars'] = node_vars

            if 'name' not in node or not node['name']:
                continue

            if node_want and node['name'] != node_want:
                continue

            nodes.append(node)
        return nodes


class DjangoSource(Source):
    """Source loading devices directly from PostgreSQL Django DB."""
    def __init__(self, cfg=None):
        super().__init__(cfg)

    def load(self, node_want=None):
        import django
        from django.apps import apps

        if not apps.ready:
            django.setup()

        from oxidized_web.models import Device, RouterDbEntry
        nodes = []

        router_db_content = RouterDbEntry.get_content()
        if router_db_content:
            delimiter = self.cfg.get('delimiter', ':') if self.cfg else ':'
            map_def = self.cfg.get('map', {'name': 0, 'model': 1, 'group': 2}) if self.cfg else {'name': 0, 'model': 1, 'group': 2}
            for line in router_db_content.splitlines():
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = [p.strip() for p in re.split(delimiter, line)]
                node = {}
                for k, pos in map_def.items():
                    if int(pos) < len(parts):
                        node[k] = parts[int(pos)]
                if node.get('name'):
                    if node_want and node['name'] != node_want:
                        continue
                    nodes.append(node)

        dev_qs = Device.objects.filter(enabled=True)
        if node_want:
            dev_qs = dev_qs.filter(name=node_want)

        dev_dict = {dev.name: dev for dev in dev_qs}

        # Populate runtime status onto any CSV/router.db defined nodes if device exists
        for n in nodes:
            dev = dev_dict.get(n['name'])
            if dev:
                n['status'] = dev.last_status
                n['last_error'] = dev.last_error
                n['attempts'] = dev.attempts
                n['time'] = dev.last_update.strftime("%Y-%m-%d %H:%M:%S") if dev.last_update else 'never'
                n['mtime'] = dev.last_changed.strftime("%Y-%m-%d %H:%M:%S") if dev.last_changed else 'never'

        existing_names = {n['name'] for n in nodes}
        for dev in dev_qs:
            if dev.name not in existing_names:
                merged_vars = dict(dev.extra_vars or {})
                if dev.ssh_kex:
                    merged_vars['ssh_kex'] = dev.ssh_kex
                if dev.ssh_hostkey:
                    merged_vars['ssh_hostkey'] = dev.ssh_hostkey
                if dev.ssh_ciphers:
                    merged_vars['ssh_ciphers'] = dev.ssh_ciphers
                if dev.ssh_clear_hostkey:
                    merged_vars['ssh_clear_hostkey'] = True
                if dev.ssh_legacy_rsa:
                    merged_vars['ssh_legacy_rsa'] = True

                nodes.append({
                    'name': dev.name,
                    'ip': dev.ip or dev.name,
                    'model': dev.model,
                    'group': dev.group or 'default',
                    'username': dev.username,
                    'password': dev.password,
                    'input': dev.input_type or 'ssh',
                    'output': dev.output_type or 'db',
                    'vars': merged_vars,
                    'ssh_kex': dev.ssh_kex,
                    'ssh_hostkey': dev.ssh_hostkey,
                    'ssh_ciphers': dev.ssh_ciphers,
                    'ssh_clear_hostkey': dev.ssh_clear_hostkey,
                    'ssh_legacy_rsa': dev.ssh_legacy_rsa,
                    'status': dev.last_status,
                    'last_error': dev.last_error,
                    'attempts': dev.attempts,
                    'time': dev.last_update.strftime("%Y-%m-%d %H:%M:%S") if dev.last_update else 'never',
                    'mtime': dev.last_changed.strftime("%Y-%m-%d %H:%M:%S") if dev.last_changed else 'never',
                })

        return nodes


SOURCE_REGISTRY = {
    'csv': CSVSource,
    'django': DjangoSource,
    'sql': DjangoSource,
    'postgres': DjangoSource,
}

def resolve_source(name, cfg=None):
    norm = str(name).lower()
    cls = SOURCE_REGISTRY.get(norm, CSVSource)
    return cls(cfg)
