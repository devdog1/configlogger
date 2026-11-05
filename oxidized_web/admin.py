from django.contrib import admin
from django import forms
from oxidized_web.models import OxidizedSetting, RouterDbEntry, Device, CustomModel, NodeRevision


class DeviceAdminForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Override password (hidden for security)"
    )

    class Meta:
        model = Device
        fields = '__all__'

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password and self.instance and self.instance.pk:
            return self.instance.password
        return password

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = []
        seen = set()
        for cm in CustomModel.objects.filter(enabled=True).order_by('name'):
            label = f"{cm.description or cm.name.capitalize()} ({cm.name})"
            choices.append((cm.name, label))
            seen.add(cm.name)

        # Fallbacks for primary models if not in custom models
        for p in ['ios', 'junos', 'eos']:
            if p not in seen:
                choices.insert(0, (p, f"{p.upper()} ({p})"))

        self.fields['model'] = forms.ChoiceField(
            choices=choices,
            initial=self.instance.model if self.instance and self.instance.pk else 'ios',
            help_text="Select device OS model from dropdown"
        )


class OxidizedSettingAdminForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Default password (hidden for security)"
    )

    class Meta:
        model = OxidizedSetting
        fields = '__all__'

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if not password and self.instance and self.instance.pk:
            return self.instance.password
        return password


@admin.register(OxidizedSetting)
class OxidizedSettingAdmin(admin.ModelAdmin):
    form = OxidizedSettingAdminForm
    list_display = ('key', 'username', 'model', 'interval', 'threads', 'output_default', 'updated_at')
    readonly_fields = ('updated_at',)

    fieldsets = (
        ('General & Credentials', {
            'fields': (
                'key',
                ('username', 'password'),
                ('model', 'resolve_dns'),
                ('log', 'use_syslog', 'debug'),
                'pid',
            ),
            'description': 'Default login credentials and general execution settings.'
        }),
        ('Worker Threads & Scheduling', {
            'fields': (
                ('interval', 'threads', 'use_max_threads'),
                ('timeout', 'retries'),
                ('prompt', 'rest', 'next_adds_job'),
            ),
            'description': 'Polling intervals, concurrency, timeouts, prompt matching regex, and REST API.'
        }),
        ('Crash Handling & Statistics', {
            'fields': (
                ('crash_directory', 'crash_hostnames'),
                'stats_history_size',
            )
        }),
        ('Input Driver Configuration', {
            'fields': (
                'input_default',
                ('input_debug', 'input_ssh_secure'),
                ('input_ftp_passive', 'input_utf8_encoded'),
            ),
            'description': 'Configure SSH, Telnet, and other input parameters.'
        }),
        ('Output Driver Configuration', {
            'fields': (
                'output_default',
                'output_file_directory',
                ('output_git_user', 'output_git_email'),
                ('output_git_repo', 'output_git_single_repo'),
            ),
            'description': 'Configure storage destinations for configs (Local filesystem, Git repository, etc.).'
        }),
        ('Source & router.db File Options', {
            'fields': (
                'source_default',
                ('source_csv_file', 'source_csv_delimiter', 'source_csv_gpg'),
                'source_csv_map',
                'source_csv_vars_map',
            ),
            'description': 'Configure default source and CSV router.db column mappings.'
        }),
        ('Advanced: Global Vars, Model Mappings & Overrides', {
            'classes': ('collapse',),
            'fields': (
                'extra_vars',
                'model_map',
                'model_overrides',
                'group_overrides',
                'hooks',
                'updated_at',
            ),
            'description': 'Model overrides, group configurations, variables (remove_secret, auth_methods), and event hooks.'
        }),
    )


@admin.register(RouterDbEntry)
class RouterDbEntryAdmin(admin.ModelAdmin):
    list_display = ('name', 'updated_at')
    fields = ('name', 'content', 'updated_at')
    readonly_fields = ('updated_at',)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    form = DeviceAdminForm
    list_display = ('name', 'ip', 'model', 'group', 'input_type', 'output_type', 'enabled', 'updated_at')
    list_filter = ('model', 'group', 'input_type', 'output_type', 'enabled')
    search_fields = ('name', 'ip', 'model', 'group')
    fieldsets = (
        (None, {
            'fields': ('name', 'ip', 'model', 'group', 'enabled')
        }),
        ('Authentication & Driver', {
            'fields': ('username', 'password', 'input_type', 'output_type')
        }),
        ('SSH Algorithm Overrides & Options', {
            'fields': ('ssh_kex', 'ssh_hostkey', 'ssh_ciphers', 'ssh_clear_hostkey'),
            'description': 'Configure per-host KexAlgorithms (+diffie-hellman-group14-sha1), HostKeyAlgorithms (+ssh-rsa), Ciphers (+aes128-cbc), or clear held signature verification keys.'
        }),
        ('Advanced Variables', {
            'fields': ('extra_vars',)
        }),
    )


@admin.register(CustomModel)
class CustomModelAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'prompt_regex', 'comment_prefix', 'enabled', 'updated_at')
    list_filter = ('enabled',)
    search_fields = ('name', 'description')
    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'enabled')
        }),
        ('Syntax & Prompts', {
            'fields': ('prompt_regex', 'comment_prefix')
        }),
        ('Commands & Filters', {
            'fields': ('commands', 'clean_filters'),
            'description': 'Ordered commands to execute, and regex filters to sanitize outputs/passwords.'
        }),
        ('Advanced Custom Code', {
            'classes': ('collapse',),
            'fields': ('code_snippet',),
            'description': 'Optional Python code snippet executed within model instance context.'
        })
    )


@admin.register(NodeRevision)
class NodeRevisionAdmin(admin.ModelAdmin):
    list_display = ('node_name', 'group', 'oid', 'author', 'created_at')
    list_filter = ('group', 'created_at')
    search_fields = ('node_name', 'group', 'oid', 'message')
    readonly_fields = ('node_name', 'group', 'oid', 'author', 'message', 'content', 'created_at')
