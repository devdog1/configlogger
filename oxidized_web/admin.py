from django.contrib import admin
from oxidized_web.models import OxidizedSetting, RouterDbEntry, Device

@admin.register(OxidizedSetting)
class OxidizedSettingAdmin(admin.ModelAdmin):
    list_display = ('key', 'updated_at')
    fields = ('key', 'config_yaml', 'updated_at')
    readonly_fields = ('updated_at',)


@admin.register(RouterDbEntry)
class RouterDbEntryAdmin(admin.ModelAdmin):
    list_display = ('name', 'updated_at')
    fields = ('name', 'content', 'updated_at')
    readonly_fields = ('updated_at',)


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
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
        ('Advanced Variables', {
            'fields': ('extra_vars',)
        }),
    )
