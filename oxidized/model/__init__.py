import importlib
import logging
from oxidized.exceptions import ModelNotFound
from oxidized.model.models import IOS, JunOS, EOS

logger = logging.getLogger("oxidized.model")

MODEL_REGISTRY = {
    'ios': IOS,
    'cisco': IOS,
    'junos': JunOS,
    'juniper': JunOS,
    'eos': EOS,
    'arista': EOS,
}

def resolve_model(name):
    norm_name = str(name).lower()
    if norm_name in MODEL_REGISTRY:
        return MODEL_REGISTRY[norm_name]

    try:
        mod = importlib.import_module(f"oxidized.model.{norm_name}")
        for attr in dir(mod):
            val = getattr(mod, attr)
            if isinstance(val, type) and attr.lower() == norm_name:
                MODEL_REGISTRY[norm_name] = val
                return val
    except ImportError:
        pass

    logger.warning("Model '%s' not found, falling back to IOS model", name)
    return IOS
