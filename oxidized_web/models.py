from django.db import models
import yaml

class OxidizedSetting(models.Model):
    """Stores the main oxidized configuration in PostgreSQL."""
    key = models.CharField(max_length=64, unique=True, default='main')
    config_yaml = models.TextField(
        help_text="Full Oxidized YAML configuration file contents.",
        default="""---
username: username
password: password
model: ios
resolve_dns: true
interval: 3600
use_max_threads: false
threads: 30
timeout: 20
retries: 3
output:
  default: git
  git:
    user: Oxidized
    email: o@example.com
    repo: ~/.config/oxidized/oxidized.git
source:
  default: django
"""
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Oxidized Configuration"
        verbose_name_plural = "Oxidized Configuration"

    def __str__(self):
        return f"Oxidized Config ({self.key})"

    @classmethod
    def get_config_yaml(cls):
        setting = cls.objects.first()
        return setting.config_yaml if setting else None


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
    output_type = models.CharField(max_length=32, default="file", help_text="Output method (file, git)")
    extra_vars = models.JSONField(default=dict, blank=True, help_text="Extra variables / credentials in JSON format")
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Device"
        verbose_name_plural = "Devices (router.db nodes)"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.model})"
