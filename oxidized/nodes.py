import logging
from oxidized.config import Config
from oxidized.exceptions import NoNodesFound
from oxidized.node import Node
from oxidized.source import resolve_source

logger = logging.getLogger("oxidized.nodes")

class Nodes(list):
    def __init__(self, opts=None):
        super().__init__()
        self.opts = opts or {}
        self.sources = []
        self._setup_sources()
        self.load()

    def _setup_sources(self):
        cfg = Config.current()
        src_name = cfg.source.default or 'django'
        self.sources.append(resolve_source(src_name, cfg.source.get(src_name)))
        if src_name != 'django':
            self.sources.append(resolve_source('django', cfg.source.get('django')))

    def load(self, node_want=None):
        raw_nodes = []
        for src in self.sources:
            try:
                found = src.load(node_want)
                if found:
                    raw_nodes.extend(found)
            except Exception as e:
                logger.debug("Source load note: %s", e)

        seen = set()
        new_nodes = []
        for r in raw_nodes:
            if r['name'] not in seen:
                seen.add(r['name'])
                new_nodes.append(Node(r))

        self.clear()
        self.extend(new_nodes)
        return self

    def get(self, name):
        for n in self:
            if n.name == name:
                return n
        return None

    def list(self):
        return [n.to_dict() for n in self]
