import pytest
from django.test import Client
from django.contrib.auth.models import User
from oxidized_web.models import OxidizedSetting, RouterDbEntry, Device

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

    client = Client()

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
    assert resp.status_code == 302

    # /reload
    resp = client.get('/reload')
    assert resp.status_code == 302

    # /nodes/stats
    resp = client.get('/nodes/stats')
    assert resp.status_code == 200

    # /nodes/stats.json
    resp = client.get('/nodes/stats.json')
    assert resp.status_code == 200
    stats = resp.json()
    assert 'total_nodes' in stats
    assert stats['total_nodes'] >= 1
