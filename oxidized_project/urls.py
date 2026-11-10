from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, re_path
from django.views.static import serve
from oxidized_web import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),

    # Authentication & Azure SSO
    path('login', views.login_view, name='login'),
    path('logout', views.logout_view, name='logout'),
    path('auth/azure/login', views.azure_login_view, name='azure_login'),
    path('auth/azure/callback', views.azure_callback_view, name='azure_callback'),

    path('nodes', views.nodes_list, name='nodes_list'),
    path('nodes.json', views.nodes_list, name='nodes_list_json'),
    path('nodes/group/<str:filter_value>', views.nodes_list, {'filter_type': 'group'}, name='nodes_group'),
    path('nodes/group/<str:filter_value>.json', views.nodes_list, {'filter_type': 'group'}, name='nodes_group_json'),
    path('nodes/model/<str:filter_value>', views.nodes_list, {'filter_type': 'model'}, name='nodes_model'),
    path('nodes/model/<str:filter_value>.json', views.nodes_list, {'filter_type': 'model'}, name='nodes_model_json'),

    path('nodes/conf_search', views.conf_search, name='conf_search'),
    path('nodes/conf_search.json', views.conf_search, name='conf_search_json'),
    path('nodes/stats', views.stats_view, name='stats_view'),
    path('nodes/stats.json', views.stats_view, name='stats_view_json'),
    path('reload', views.reload_nodes, name='reload_nodes'),
    path('reload.json', views.reload_nodes, name='reload_nodes_json'),

    # Daemon Management & Process Control
    path('daemon', views.daemon_control_view, name='daemon_control'),
    path('daemon/status', views.daemon_status_api, name='daemon_status_api'),
    path('daemon/status.json', views.daemon_status_api, name='daemon_status_api_json'),
    path('daemon/reload', views.daemon_reload_view, name='daemon_reload'),
    path('daemon/reload.json', views.daemon_reload_view, name='daemon_reload_json'),
    path('daemon/restart', views.daemon_restart_view, name='daemon_restart'),
    path('daemon/restart.json', views.daemon_restart_view, name='daemon_restart_json'),

    path('node/show/<str:node>', views.node_show, name='node_show'),
    path('node/show/<str:node>.json', views.node_show, name='node_show_json'),
    path('node/fetch/<str:node>', views.node_fetch, name='node_fetch'),
    path('node/fetch/<str:group>/<str:node>', views.node_fetch, name='node_fetch_grouped'),
    path('node/next/<str:node>', views.node_next, name='node_next'),
    path('node/next/<str:group>/<str:node>', views.node_next, name='node_next_grouped'),

    path('node/version', views.node_version, name='node_version'),
    path('node/version.json', views.node_version, name='node_version_json'),
    path('node/version/view', views.node_version_view, name='node_version_view'),
    path('node/version/view.json', views.node_version_view, name='node_version_view_json'),
    path('node/version/diffs', views.node_version_diffs, name='node_version_diffs'),

    # User Configuration Pages (Outside of Django Admin)
    path('devices', views.device_list_view, name='device_list_view'),
    path('devices/add', views.device_create_view, name='device_create_view'),
    path('devices/<int:pk>/edit', views.device_edit_view, name='device_edit_view'),
    path('devices/<int:pk>/delete', views.device_delete_view, name='device_delete_view'),

    path('models', views.model_list_view, name='model_list_view'),
    path('models/add', views.model_create_view, name='model_create_view'),
    path('models/<int:pk>/edit', views.model_edit_view, name='model_edit_view'),
    path('models/<int:pk>/delete', views.model_delete_view, name='model_delete_view'),

    # Fallback static handler ensuring static files are served across all environments
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.BASE_DIR / 'oxidized_web' / 'static'}),
]
