import pytest
from django.test import Client
from django.contrib.auth.models import User
from oxidized_web.models import OxidizedSetting, RouterDbEntry, Device, CustomModel
from oxidized.output import GitOutput
import tempfile
import shutil

@pytest.mark.django_db
def test_django_admin_access():
    User.objects.filter(username='admin').delete()
    admin_user = User.objects.create_superuser('admin', 'admin@test.com', 'adminpass')
    client = Client()
    client.force_login(admin_user)

    # Admin home
    resp = client.get('/admin/')
    assert resp.status_code == 200

    # OxidizedSetting admin list
    resp = client.get('/admin/oxidized_web/oxidizedsetting/')
    assert resp.status_code == 200

    # RouterDbEntry admin list
    resp = client.get('/admin/oxidized_web/routerdbentry/')
    assert resp.status_code == 200

    # Device admin list
    resp = client.get('/admin/oxidized_web/device/')
    assert resp.status_code == 200

    # CustomModel admin list
    resp = client.get('/admin/oxidized_web/custommodel/')
    assert resp.status_code == 200

@pytest.mark.django_db
def test_oxidized_web_views_and_api():
    Device.objects.all().delete()
    Device.objects.create(
        name='router-test',
        ip='10.10.10.1',
        model='ios',
        group='edge',
        input_type='mock'
    )

    admin_user = User.objects.create_superuser('admin_user', 'admin@test.com', 'adminpass')
    client = Client()
    client.force_login(admin_user)

    # / redirect to /nodes
    resp = client.get('/')
    assert resp.status_code == 302
    assert resp.url == '/nodes'

    # /nodes HTML
    resp = client.get('/nodes')
    assert resp.status_code == 200
    assert b'router-test' in resp.content

    # /nodes.json
    resp = client.get('/nodes.json')
    assert resp.status_code == 200
    json_data = resp.json()
    assert any(n['name'] == 'router-test' for n in json_data)

    # /nodes/group/edge
    resp = client.get('/nodes/group/edge')
    assert resp.status_code == 200
    assert b'router-test' in resp.content

    # /node/show/router-test
    resp = client.get('/node/show/router-test')
    assert resp.status_code == 200
    assert b'router-test' in resp.content

    # /node/show/router-test.json
    resp = client.get('/node/show/router-test.json')
    assert resp.status_code == 200
    assert resp.json()['name'] == 'router-test'

    # /node/fetch/router-test
    resp = client.get('/node/fetch/router-test')
    assert resp.status_code == 200
    assert len(resp.content) > 0

    # /node/next/router-test
    resp = client.get('/node/next/router-test')
    assert resp.status_code == 200
    assert resp.json().get('queued') is True

    # Test rapid pull prevention: immediate repeated call within cooldown returns 429
    resp_rapid = client.get('/node/next/router-test')
    assert resp_rapid.status_code == 429
    assert resp_rapid.json().get('queued') is False

    # /reload
    resp = client.get('/reload')
    assert resp.status_code == 200
    assert resp.json().get('reloaded') is True

    # /nodes/stats
    resp = client.get('/nodes/stats')
    assert resp.status_code == 200

    # /nodes/stats.json
    resp = client.get('/nodes/stats.json')
    assert resp.status_code == 200
    stats = resp.json()
    assert 'total_nodes' in stats
    assert stats['total_nodes'] >= 1

@pytest.mark.django_db
def test_revision_control_and_git_diff_view():
    tmp_git = tempfile.mkdtemp()
    try:
        git_out = GitOutput({'repo': tmp_git, 'user': 'Tester', 'email': 't@example.com'})
        git_out.store('core-switch', "hostname core-switch\ninterface GigabitEthernet0/1\n  shutdown\n")
        git_out.store('core-switch', "hostname core-switch\ninterface GigabitEthernet0/1\n  no shutdown\n")

        Device.objects.filter(name='core-switch').delete()
        dev = Device.objects.create(
            name='core-switch',
            ip='10.0.0.10',
            model='ios',
            group='core',
            output_type='git'
        )

        admin_user = User.objects.create_superuser('admin_user2', 'admin2@test.com', 'adminpass')
        client = Client()
        client.force_login(admin_user)

        # Check /node/version
        resp = client.get('/node/version?node_full=core-switch')
        assert resp.status_code == 200
        assert b'core-switch' in resp.content

        # Check /node/version.json
        resp_json = client.get('/node/version.json?node_full=core-switch')
        assert resp_json.status_code == 200
        versions = resp_json.json().get('versions', [])

        # Check /node/version/diffs git-style view
        resp_diff = client.get('/node/version/diffs?node_full=core-switch')
        assert resp_diff.status_code == 200
        assert b'Diff Comparison' in resp_diff.content
    finally:
        shutil.rmtree(tmp_git, ignore_errors=True)
