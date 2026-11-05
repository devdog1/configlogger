from django.db import models

class OxidizedSetting(models.Model):
    """Stores the main oxidized configuration in PostgreSQL with structured parameters."""
    key = models.CharField(max_length=64, unique=True, default='main')

    # General & Authentication
    username = models.CharField(max_length=128, default='username', blank=True, help_text="Default username for devices")
    password = models.CharField(max_length=128, default='password', blank=True, help_text="Default password for devices")
    model = models.CharField(max_length=64, default='ios', help_text="Default model type (e.g. ios, junos, eos)")
    resolve_dns = models.BooleanField(default=True, help_text="Resolve DNS to IP address")
    interval = models.IntegerField(default=43200, help_text="How often configs are gathered in seconds (e.g. 43200 = 12h)")
    log = models.CharField(max_length=255, default='~/.config/oxidized/logs/oxidized.log', blank=True, help_text="Log file location")
    use_syslog = models.BooleanField(default=False, help_text="Send log output to syslog")
    debug = models.BooleanField(default=False, help_text="Enable verbose debug logging")
    threads = models.IntegerField(default=30, help_text="Worker threads count (e.g. 30 or 200)")
    use_max_threads = models.BooleanField(default=False, help_text="Always use max threads")
    timeout = models.IntegerField(default=20, help_text="Device connection/execution timeout in seconds")
    retries = models.IntegerField(default=3, help_text="Number of retries upon failure")
    prompt = models.CharField(max_length=255, default=r'^([\w.@-]+[#>]\s?)$', help_text="Regex for device prompt")
    rest = models.CharField(max_length=64, default='0.0.0.0:8888', blank=True, help_text="REST API listen address")
    next_adds_job = models.BooleanField(default=True, help_text="Move next item immediately to top of queue ahead of other items")
    pid = models.CharField(max_length=255, default='~/.config/oxidized/pid', blank=True, help_text="PID file path")

    # Crash & Stats
    crash_directory = models.CharField(max_length=255, default='~/.config/oxidized/crashes', blank=True)
    crash_hostnames = models.BooleanField(default=False)
    stats_history_size = models.IntegerField(default=10, help_text="Number of recent job runs to retain in stats history")

    # Input Settings
    input_default = models.CharField(max_length=64, default='ssh', help_text="Default input mechanism (e.g. ssh, telnet)")
    input_debug = models.BooleanField(default=False, help_text="Debug input sessions")
    input_ssh_secure = models.BooleanField(default=False, help_text="Enforce strict SSH host key checking")
    input_ftp_passive = models.BooleanField(default=True)
    input_utf8_encoded = models.BooleanField(default=True)

    # Output Settings
    output_default = models.CharField(max_length=64, default='db', help_text="Default output mechanism (db, file, git)")
    output_file_directory = models.CharField(max_length=255, default='', blank=True, help_text="Optional local file output directory")
    output_git_user = models.CharField(max_length=128, default='Oxidized', blank=True)
    output_git_email = models.CharField(max_length=128, default='o@example.com', blank=True)
    output_git_repo = models.CharField(max_length=255, default='', blank=True, help_text="Optional git repository path")
    output_git_single_repo = models.BooleanField(default=True)

    # Source Settings
    source_default = models.CharField(max_length=64, default='django', help_text="Default source (django, csv)")
    source_csv_file = models.CharField(max_length=255, default='~/.config/oxidized/router.db', blank=True)
    source_csv_delimiter = models.CharField(max_length=16, default=':', blank=True)
    source_csv_map = models.JSONField(default=dict, blank=True, help_text='CSV field mapping, e.g. {"name": 0, "model": 1, "group": 2}')
    source_csv_vars_map = models.JSONField(default=dict, blank=True, help_text='CSV vars mapping, e.g. {"ssh_kex": 3, "remove_secret": 4}')
    source_csv_gpg = models.BooleanField(default=False)

    # Global Vars, Model Map, Model Overrides, Groups, Hooks
    extra_vars = models.JSONField(
        default=dict,
        blank=True,
        help_text='Global vars, e.g. {"auth_methods": ["password", "keyboard-interactive"], "remove_secret": false}'
    )
    model_map = models.JSONField(
        default=dict,
        blank=True,
        help_text='Maps friendly aliases to model names, e.g. {"cisco": "ios", "juniper": "junos"}'
    )
    model_overrides = models.JSONField(
        default=dict,
        blank=True,
        help_text='Model-level credentials or config overrides, e.g. {"routeros": {"username": "user", "password": "pass"}}'
    )
    group_overrides = models.JSONField(
        default=dict,
        blank=True,
        help_text='Group configurations, e.g. {"core": {}, "switches": {}}'
    )
    hooks = models.JSONField(
        default=dict,
        blank=True,
        help_text='Configured hooks, e.g. {"push_to_remote": {"type": "githubrepo", "events": ["post_store"]}, "email_output": {"type": "exec"}}'
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Oxidized Configuration"
        verbose_name_plural = "Oxidized Configuration"

    def __str__(self):
        return f"Oxidized Configuration ({self.key})"

    def to_dict(self):
        """Convert the structured settings into Oxidized configuration dictionary."""
        return {
            'username': self.username,
            'password': self.password,
            'model': self.model,
            'resolve_dns': self.resolve_dns,
            'interval': self.interval,
            'log': self.log,
            'use_syslog': self.use_syslog,
            'debug': self.debug,
            'threads': self.threads,
            'use_max_threads': self.use_max_threads,
            'timeout': self.timeout,
            'retries': self.retries,
            'prompt': self.prompt,
            'rest': self.rest,
            'next_adds_job': self.next_adds_job,
            'pid': self.pid,
            'crash': {
                'directory': self.crash_directory,
                'hostnames': self.crash_hostnames,
            },
            'stats': {
                'history_size': self.stats_history_size,
            },
            'input': {
                'default': self.input_default,
                'debug': self.input_debug,
                'ssh': {
                    'secure': self.input_ssh_secure,
                },
                'ftp': {
                    'passive': self.input_ftp_passive,
                },
                'utf8_encoded': self.input_utf8_encoded,
            },
            'output': {
                'default': self.output_default,
                'file': {
                    'directory': self.output_file_directory,
                },
                'git': {
                    'user': self.output_git_user,
                    'email': self.output_git_email,
                    'repo': self.output_git_repo,
                    'single_repo': self.output_git_single_repo,
                },
            },
            'source': {
                'default': self.source_default,
                'csv': {
                    'file': self.source_csv_file,
                    'delimiter': self.source_csv_delimiter,
                    'map': self.source_csv_map or {'name': 0, 'model': 1, 'group': 2},
                    'vars_map': self.source_csv_vars_map or {},
                    'gpg': self.source_csv_gpg,
                },
                'django': {
                    'app': 'oxidized_web',
                },
            },
            'vars': self.extra_vars or {},
            'model_map': self.model_map or {
                'CableOS': 'CableOS',
                'juniper': 'junos',
                'cisco': 'ios',
                'mikrotik': 'routeros',
                'fortigate': 'fortios',
                'arista': 'eos',
            },
            'models': self.model_overrides or {},
            'groups': self.group_overrides or {},
            'hooks': self.hooks or {},
        }

    @classmethod
    def get_config_dict(cls):
        setting = cls.objects.first()
        return setting.to_dict() if setting else None


class RouterDbEntry(models.Model):
    """Stores the raw router.db content or serves as editable router.db file in Postgres."""
    name = models.CharField(max_length=64, unique=True, default='router.db')
    content = models.TextField(
        help_text="router.db file content (CSV format, e.g. name:model:group or name:ip:model:username:password).",
        blank=True,
        default="# router.db\n# name:model:group\n"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "router.db File"
        verbose_name_plural = "router.db File"

    def __str__(self):
        return self.name

    @classmethod
    def get_content(cls):
        entry = cls.objects.first()
        return entry.content if entry else ""


class Device(models.Model):
    """Structured network node / device stored in PostgreSQL."""
    name = models.CharField(max_length=255, unique=True, help_text="Device hostname or identifier")
    ip = models.CharField(max_length=255, blank=True, help_text="IP address or FQDN (defaults to name)")
    model = models.CharField(max_length=64, default="ios", help_text="Oxidized model (e.g. ios, junos, eos)")
    group = models.CharField(max_length=64, default="default", blank=True)
    username = models.CharField(max_length=128, blank=True, help_text="Override username")
    password = models.CharField(max_length=128, blank=True, help_text="Override password")
    input_type = models.CharField(max_length=32, default="ssh", help_text="Input method (ssh, telnet, exec, mock)")
    output_type = models.CharField(max_length=32, default="db", help_text="Output method (db, file, git)")
    interval = models.IntegerField(null=True, blank=True, help_text="Per-host collection interval in seconds (overrides system interval if set)")
    extra_vars = models.JSONField(default=dict, blank=True, help_text="Extra variables / credentials in JSON format")
    enabled = models.BooleanField(default=True)

    # Advanced SSH Options per host (Kex, HostKey, Ciphers, Legacy SSH-RSA)
    ssh_kex = models.CharField(max_length=255, blank=True, default="", help_text="Override KexAlgorithms, e.g. +diffie-hellman-group14-sha1 or diffie-hellman-group1-sha1")
    ssh_hostkey = models.CharField(max_length=255, blank=True, default="", help_text="Override HostKeyAlgorithms, e.g. +ssh-rsa,rsa-sha2-512")
    ssh_ciphers = models.CharField(max_length=255, blank=True, default="", help_text="Override Ciphers, e.g. +aes128-cbc,aes256-cbc")
    ssh_clear_hostkey = models.BooleanField(default=False, help_text="Ignore / clear held hostkey verification errors (AutoAddPolicy)")
    ssh_legacy_rsa = models.BooleanField(default=False, help_text="Force legacy SSH-RSA by disabling rsa-sha2-256 and rsa-sha2-512 algorithms")

    # Runtime Status Tracking
    last_status = models.CharField(max_length=32, default="never", help_text="Last backup status (success, fail, no_connection, never)")
    last_error = models.TextField(blank=True, default="", help_text="Last error or failure reason")
    attempts = models.IntegerField(default=0, help_text="Number of attempts during last backup")
    last_update = models.DateTimeField(null=True, blank=True, help_text="Timestamp of last backup run attempt")
    last_changed = models.DateTimeField(null=True, blank=True, help_text="Timestamp when config last changed")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Device"
        verbose_name_plural = "Devices (router.db nodes)"
        ordering = ['name']
        permissions = [
            ("can_view_node", "Can view node and its details"),
            ("can_edit_node", "Can edit node parameters"),
            ("can_delete_node", "Can delete node"),
            ("can_pull_node", "Can trigger node pull/refresh"),
            ("can_edit_config", "Can edit oxidized configurations and settings"),
        ]

    def __str__(self):
        return f"{self.name} ({self.model})"


class CustomModel(models.Model):
    """Custom Node Model defined via Django Admin."""
    name = models.CharField(max_length=64, unique=True, help_text="Model identifier, e.g. 'routeros', 'fortios', 'vyos'")
    description = models.CharField(max_length=255, blank=True, help_text="Short description of OS/Platform")
    prompt_regex = models.CharField(max_length=255, default=r'^([\w.@-]+[#>]\s?)$', help_text="Device prompt regex pattern")
    comment_prefix = models.CharField(max_length=128, default="! ", help_text="Comment prefix, e.g. '! ' or '# '")
    commands = models.JSONField(
        default=list,
        blank=True,
        help_text='List of commands to execute, e.g. ["show version", "show running-config"] or [{"cmd": "export", "input": "ssh"}]'
    )
    clean_filters = models.JSONField(
        default=list,
        blank=True,
        help_text='List of regex replace pairs to sanitize output, e.g. [["password \\\\S+", "password <secret hidden>"]]'
    )
    code_snippet = models.TextField(
        blank=True,
        help_text="Optional custom Python code executing within Model context to customize logic"
    )
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Custom Node Model"
        verbose_name_plural = "Custom Node Models"
        ordering = ['name']
        permissions = [
            ("can_view_model", "Can view node model"),
            ("can_edit_model", "Can edit node model"),
            ("can_delete_model", "Can delete node model"),
        ]

    def __str__(self):
        return f"Model: {self.name}"


class NodeRevision(models.Model):
    """Device configuration revision stored directly in the local PostgreSQL database."""
    node_name = models.CharField(max_length=255, db_index=True)
    group = models.CharField(max_length=64, default="default", blank=True, db_index=True)
    oid = models.CharField(max_length=64, unique=True, db_index=True, help_text="Revision hash / identifier")
    author = models.CharField(max_length=255, default="Oxidized <oxidized@localhost>")
    message = models.TextField(blank=True)
    content = models.TextField(help_text="Full configuration backup text")
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = "Node Revision"
        verbose_name_plural = "Node Revisions (History in PostgreSQL)"
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.node_name} @ {self.oid[:8]} ({self.created_at.strftime('%Y-%m-%d %H:%M:%S')})"
