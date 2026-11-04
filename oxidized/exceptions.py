"""Oxidized - Network device configuration backup tool in Python."""

__version__ = "0.29.0"

class OxidizedError(Exception):
    pass

class NoConfig(OxidizedError):
    pass

class InvalidConfig(OxidizedError):
    pass

class MethodNotFound(OxidizedError):
    pass

class ModelNotFound(OxidizedError):
    pass

class NoNodesFound(OxidizedError):
    pass
