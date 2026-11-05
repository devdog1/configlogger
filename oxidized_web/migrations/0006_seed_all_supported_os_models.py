import json
import os
from django.db import migrations

def seed_models(apps, schema_editor):
    CustomModel = apps.get_model('oxidized_web', 'CustomModel')
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'oxidized', 'model', 'models_data.json')
    if not os.path.exists(json_path):
        return
    with open(json_path, 'r', encoding='utf-8') as f:
        models_data = json.load(f)

    for name, data in models_data.items():
        cls_name = data.get('class_name', name.capitalize())
        desc = f"{cls_name} ({name})"
        prompt = data.get('prompt', r'^([\w.@-]+[#>]\s?)$')
        comment = data.get('comment', '! ')
        cmds = data.get('cmds', ['show running-config'])

        CustomModel.objects.get_or_create(
            name=name.lower(),
            defaults={
                'description': desc,
                'prompt_regex': prompt,
                'comment_prefix': comment,
                'commands': cmds,
                'enabled': True
            }
        )

def unseed_models(apps, schema_editor):
    pass

class Migration(migrations.Migration):
    dependencies = [
        ('oxidized_web', '0005_alter_custommodel_comment_prefix'),
    ]

    operations = [
        migrations.RunPython(seed_models, unseed_models),
    ]
