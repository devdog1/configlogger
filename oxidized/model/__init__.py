import os
import json
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

# Load all built-in Oxidized models from models_data.json
BUILTIN_MODELS_DATA = {}
models_json_path = os.path.join(os.path.dirname(__file__), "models_data.json")
if os.path.exists(models_json_path):
    try:
        with open(models_json_path, "r", encoding="utf-8") as f:
            BUILTIN_MODELS_DATA = json.load(f)
    except Exception as e:
        logger.error("Failed to load models_data.json: %s", e)


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
    raw_filters = custom_model_obj.clean_filters or []
    if isinstance(raw_filters, str):
        try:
            raw_filters = json.loads(raw_filters)
        except Exception:
            raw_filters = []

    filters = raw_filters if isinstance(raw_filters, list) else []
    if filters:
        def _clean_regex(self, cfg, cmd=""):
            for f in filters:
                pat, repl = None, None
                if isinstance(f, (list, tuple)) and len(f) >= 2:
                    pat, repl = f[0], f[1]
                elif isinstance(f, str):
                    try:
                        parsed_f = json.loads(f)
                        if isinstance(parsed_f, (list, tuple)) and len(parsed_f) >= 2:
                            pat, repl = parsed_f[0], parsed_f[1]
                    except Exception:
                        pass
                elif isinstance(f, dict):
                    pat = f.get('pattern') or f.get('regex') or f.get('match')
                    repl = f.get('replace') if 'replace' in f else f.get('replacement', '')
                if pat is not None and repl is not None:
                    try:
                        cfg = re.sub(str(pat), str(repl), cfg, flags=re.MULTILINE)
                    except Exception as err:
                        logger.error("Regex replacement error for model %s (pattern %s): %s", custom_model_obj.name, pat, err)
            return cfg

        # Register as :all filter so it always performs the regex replacement before writing to DB or showing config
        dynamic_cls.add_all(_clean_regex)

    # Execute custom code snippet if present
    if custom_model_obj.code_snippet:
        try:
            scope = {'Model': dynamic_cls, 're': re}
            exec(custom_model_obj.code_snippet, scope)
        except Exception as e:
            logger.error("Error evaluating custom code for model %s: %s", custom_model_obj.name, e)

    return dynamic_cls


def build_builtin_model(name, data):
    """Build a Model class definition from data extracted from Oxidized upstream models."""
    class_name = data.get('class_name') or name.capitalize()
    model_cls = type(class_name, (Model,), {})
    model_cls._comment = data.get('comment', '! ')
    model_cls._prompt = data.get('prompt', r'^([\w.@()-]+[#>]\s?)$')

    cmds = data.get('cmds', ['show running-config'])
    for c in cmds:
        model_cls.add_cmd(c)

    return model_cls


def resolve_model(name):
    norm_name = str(name).lower()
    if norm_name in MODEL_REGISTRY:
        return MODEL_REGISTRY[norm_name]

    # Check CustomModel in Django DB
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

    # Check Built-in models from models_data.json
    if norm_name in BUILTIN_MODELS_DATA:
        built_cls = build_builtin_model(norm_name, BUILTIN_MODELS_DATA[norm_name])
        MODEL_REGISTRY[norm_name] = built_cls
        return built_cls

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
