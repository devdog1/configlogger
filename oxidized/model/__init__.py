import importlib
import logging
import re
from oxidized.exceptions import ModelNotFound
from oxidized.model.model import Model
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

def create_dynamic_model(custom_model_obj):
    """Generate a Model subclass dynamically from a CustomModel DB record."""
    model_name = custom_model_obj.name.capitalize()
    dynamic_cls = type(model_name, (Model,), {})
    dynamic_cls._comment = custom_model_obj.comment_prefix or "! "
    dynamic_cls._prompt = custom_model_obj.prompt_regex or r'^([\w.@-]+[#>]\s?)$'

    # Add commands
    commands = custom_model_obj.commands or ["show running-config"]
    for cmd_item in commands:
        if isinstance(cmd_item, str):
            dynamic_cls.add_cmd(cmd_item)
        elif isinstance(cmd_item, dict):
            cmd_str = cmd_item.get('cmd')
            if cmd_str:
                dynamic_cls.add_cmd(cmd_str, input=cmd_item.get('input'))

    # Add regex filters
    filters = custom_model_obj.clean_filters or []
    if filters:
        def _clean_secret(self, cfg, cmd=""):
            for f in filters:
                if isinstance(f, (list, tuple)) and len(f) >= 2:
                    pat, repl = f[0], f[1]
                    cfg = re.sub(pat, repl, cfg, flags=re.MULTILINE)
            return cfg
        dynamic_cls.add_secret(_clean_secret)

    # Execute custom code snippet if present
    if custom_model_obj.code_snippet:
        try:
            scope = {'Model': dynamic_cls, 're': re}
            exec(custom_model_obj.code_snippet, scope)
        except Exception as e:
            logger.error("Error evaluating custom code for model %s: %s", custom_model_obj.name, e)

    return dynamic_cls


def resolve_model(name):
    norm_name = str(name).lower()
    if norm_name in MODEL_REGISTRY:
        return MODEL_REGISTRY[norm_name]

    try:
        import django
        from django.apps import apps
        if apps.ready:
            from oxidized_web.models import CustomModel
            cm = CustomModel.objects.filter(name__iexact=norm_name, enabled=True).first()
            if cm:
                dyn_cls = create_dynamic_model(cm)
                MODEL_REGISTRY[norm_name] = dyn_cls
                return dyn_cls
    except Exception as e:
        logger.debug("Database model lookup note: %s", e)

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
