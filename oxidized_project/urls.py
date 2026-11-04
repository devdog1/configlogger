from django.contrib import admin
from django.urls import path, re_path
from oxidized_web import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.index, name='index'),

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

    path('node/show/<str:node>', views.node_show, name='node_show'),
    path('node/fetch/<str:node>', views.node_fetch, name='node_fetch'),
    path('node/fetch/<str:group>/<str:node>', views.node_fetch, name='node_fetch_grouped'),
    path('node/next/<str:node>', views.node_next, name='node_next'),
    path('node/next/<str:group>/<str:node>', views.node_next, name='node_next_grouped'),

    path('node/version', views.node_version, name='node_version'),
    path('node/version.json', views.node_version, name='node_version_json'),
    path('node/version/view', views.node_version_view, name='node_version_view'),
    path('node/version/view.json', views.node_version_view, name='node_version_view_json'),
    path('node/version/diffs', views.node_version_diffs, name='node_version_diffs'),
]
