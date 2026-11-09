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

    # /daemon control page
    resp = client.get('/daemon')
    assert resp.status_code == 200
    assert b'Daemon Control' in resp.content

    # /daemon/status API
    resp = client.get('/daemon/status')
    assert resp.status_code == 200
    assert 'running' in resp.json()

    # /daemon/reload API
    resp = client.post('/daemon/reload.json')
    assert resp.status_code == 200
    assert resp.json()['status'] == 'ok'

    # /daemon/restart API
    resp = client.post('/daemon/restart.json')
    assert resp.status_code == 200
    assert 'restarted' in resp.json()

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

@pytest.mark.django_db
def test_user_device_and_model_pages():
    admin_user = User.objects.create_superuser('user_mgmt', 'user_mgmt@test.com', 'adminpass')
    client = Client()
    client.force_login(admin_user)

    # 1. Device list
    resp = client.get('/devices')
    assert resp.status_code == 200
    assert b'Configured Devices' in resp.content

    # 2. Add device
    resp_create = client.post('/devices/add', {
        'name': 'sw-user-new',
        'ip': '192.168.99.1',
        'model': 'ios',
        'group': 'default',
        'input_type': 'ssh',
        'output_type': 'db',
        'interval': 300,
        'enabled': True,
    })
    assert resp_create.status_code == 302
    assert Device.objects.filter(name='sw-user-new').exists()
    dev = Device.objects.get(name='sw-user-new')
    assert dev.interval == 300

    # 3. Edit device
    resp_edit = client.post(f'/devices/{dev.pk}/edit', {
        'name': 'sw-user-new',
        'ip': '192.168.99.2',
        'model': 'ios',
        'group': 'branch',
        'input_type': 'ssh',
        'output_type': 'db',
        'interval': 600,
        'enabled': True,
    })
    assert resp_edit.status_code == 302
    dev.refresh_from_db()
    assert dev.ip == '192.168.99.2'
    assert dev.group == 'branch'
    assert dev.interval == 600

    # 4. Model list
    resp_models = client.get('/models')
    assert resp_models.status_code == 200
    assert b'Supported OS Models' in resp_models.content

    # 5. Add custom model
    resp_model_create = client.post('/models/add', {
        'name': 'custom_switch_os',
        'description': 'Custom Switch Platform',
        'prompt_regex': r'^[a-z0-9]+#',
        'comment_prefix': '! ',
        'commands': '["show system", "show config"]',
        'clean_filters': '[]',
        'enabled': True,
    })
    assert resp_model_create.status_code == 302
    assert CustomModel.objects.filter(name='custom_switch_os').exists()


@pytest.mark.django_db
def test_authentication_required_to_view_information(client):
    """Verify that unauthenticated users cannot view nodes, devices, models, diffs, or stats."""
    # Attempting to access protected endpoints without login redirects to /login
    for path in ['/nodes', '/devices', '/models', '/nodes/stats', '/node/version/diffs', '/daemon']:
        resp = client.get(path)
        assert resp.status_code == 302
        assert resp.url.startswith('/login')


@pytest.mark.django_db
def test_local_user_authentication(client):
    """Verify standard local user login and logout."""
    User.objects.create_user(username='alice', password='password123', is_staff=True)

    # 1. Failed login
    resp_fail = client.post('/login', {'username': 'alice', 'password': 'wrongpassword'})
    assert resp_fail.status_code == 200
    assert b"Invalid username or password" in resp_fail.content

    # 2. Successful login
    resp_success = client.post('/login', {'username': 'alice', 'password': 'password123', 'next': '/nodes'})
    assert resp_success.status_code == 302
    assert resp_success.url == '/nodes'

    # 3. Can access protected page now
    resp_nodes = client.get('/nodes')
    assert resp_nodes.status_code == 200
    assert b'alice' in resp_nodes.content

    # 4. Logout
    resp_logout = client.get('/logout')
    assert resp_logout.status_code == 302
    assert resp_logout.url == '/login'

    # 5. Accessing nodes again redirects to login
    resp_nodes_after = client.get('/nodes')
    assert resp_nodes_after.status_code == 302


@pytest.mark.django_db
def test_azure_entra_id_sso_flow(client, monkeypatch):
    """Verify Azure / Entra ID SSO login flow, callback token parsing, and user auto-provisioning."""
    from oxidized_web.models import OxidizedSetting
    setting, _ = OxidizedSetting.objects.get_or_create(key='default')
    setting.azure_sso_enabled = True
    setting.azure_tenant_id = 'test-tenant-id'
    setting.azure_client_id = 'test-client-id'
    setting.azure_client_secret = 'test-client-secret'
    setting.save()

    # Login page displays Entra ID button
    resp_login = client.get('/login')
    assert resp_login.status_code == 200
    assert b"Sign in with Microsoft Entra ID" in resp_login.content

    # Mock MSAL app
    class MockMSALApp:
        def __init__(self, *args, **kwargs):
            pass

        def get_authorization_request_url(self, scopes=None, redirect_uri=None, state=None):
            return f"https://login.microsoftonline.com/test-tenant-id/oauth2/v2.0/authorize?client_id=test-client-id&state={state}"

        def acquire_token_by_authorization_code(self, code=None, scopes=None, redirect_uri=None):
            if code == 'valid_code':
                return {
                    'id_token_claims': {
                        'preferred_username': 'entra.user@example.com',
                        'email': 'entra.user@example.com',
                        'given_name': 'Entra',
                        'family_name': 'Engineer',
                    }
                }
            return {'error': 'invalid_grant', 'error_description': 'Code expired or invalid'}

    import msal
    monkeypatch.setattr(msal, 'ConfidentialClientApplication', MockMSALApp)

    # 1. Initiate Azure login
    resp_azure_login = client.get('/auth/azure/login?next=/devices')
    assert resp_azure_login.status_code == 302
    assert 'login.microsoftonline.com' in resp_azure_login.url

    # 2. Azure callback with valid code
    resp_callback = client.get('/auth/azure/callback?code=valid_code&state=/devices')
    assert resp_callback.status_code == 302
    assert resp_callback.url == '/devices'

    # Verify user was created in Django User model
    assert User.objects.filter(username='entra.user@example.com').exists()
    user = User.objects.get(username='entra.user@example.com')
    assert user.first_name == 'Entra'
    assert user.last_name == 'Engineer'
    assert user.email == 'entra.user@example.com'

    # Verify authenticated session can access /nodes
    resp_nodes = client.get('/nodes')
    assert resp_nodes.status_code == 200
    assert b'entra.user@example.com' in resp_nodes.content

    # If granted staff/device permissions, can also access /devices
    user.is_staff = True
    user.save()
    resp_devices = client.get('/devices')
    assert resp_devices.status_code == 200
    assert b'entra.user@example.com' in resp_devices.content


@pytest.mark.django_db
def test_admin_azure_secret_hidden_and_preserved(client):
    """Verify azure_client_secret is rendered with password widget and value is preserved when empty."""
    from oxidized_web.models import OxidizedSetting
    from oxidized_web.admin import OxidizedSettingAdminForm

    setting, _ = OxidizedSetting.objects.get_or_create(
        key='default',
        defaults={'azure_client_secret': 'super-secret-azure-key'}
    )
    setting.azure_client_secret = 'super-secret-azure-key'
    setting.save()

    form = OxidizedSettingAdminForm(instance=setting)
    assert form.fields['azure_client_secret'].widget.input_type == 'password'
    assert not form.fields['azure_client_secret'].widget.render_value

    # Submitting empty value should preserve existing secret
    data = {k: form[k].value() for k in form.fields}
    data['azure_client_secret'] = ''
    bound_form = OxidizedSettingAdminForm(data=data, instance=setting)
    assert bound_form.is_valid(), bound_form.errors
    assert bound_form.cleaned_data['azure_client_secret'] == 'super-secret-azure-key'


@pytest.mark.django_db
def test_sidebar_hidden_when_unauthenticated(client):
    """Verify the sidebar navigation menu is not rendered when unauthenticated."""
    resp = client.get('/login')
    assert resp.status_code == 200
    assert b'id="ox-sidebar"' not in resp.content
    assert b'ox-layout-anonymous' in resp.content

    # When authenticated, sidebar is present
    user = User.objects.create_user(username='bob', password='password123', is_staff=True)
    client.force_login(user)
    resp_logged = client.get('/nodes')
    assert resp_logged.status_code == 200
    assert b'id="ox-sidebar"' in resp_logged.content


@pytest.mark.django_db
def test_split_screen_diff_page_with_line_numbers_and_sync(client):
    """Verify split diff comparison page renders both configs side by side with line numbers and +/-."""
    from oxidized_web.models import NodeRevision
    user = User.objects.create_user(username='carol', password='password123', is_staff=True)
    client.force_login(user)

    dev, _ = Device.objects.get_or_create(
        name='sw-diff-test',
        defaults={'ip': '10.10.10.5', 'model': 'ios', 'output_type': 'db'}
    )

    r1 = NodeRevision.objects.create(
        node_name='sw-diff-test',
        group='default',
        oid='rev001',
        content='hostname sw-diff-test\ninterface Gi0/1\n shutdown\n'
    )
    r2 = NodeRevision.objects.create(
        node_name='sw-diff-test',
        group='default',
        oid='rev002',
        content='hostname sw-diff-test\ninterface Gi0/1\n no shutdown\n'
    )

    resp = client.get(f'/node/version/diffs?node_full=sw-diff-test&oid1={r1.oid}&oid2={r2.oid}')
    assert resp.status_code == 200
    assert b'diffScrollLeft' in resp.content
    assert b'diffScrollRight' in resp.content
    assert b'ox-diff-del' in resp.content
    assert b'ox-diff-add' in resp.content
    assert b'-' in resp.content
    assert b'+' in resp.content
    assert b'sw-diff-test' in resp.content


@pytest.mark.django_db
def test_clean_filters_fortios_regex_scrubbing():
    """Verify that clean_filters handles FortiOS passwords and JSON strings."""
    from oxidized.model import create_dynamic_model
    from oxidized_web.models import CustomModel

    cm, _ = CustomModel.objects.get_or_create(
        name='fortios_test_model',
        defaults={
            'clean_filters': '[["(set (?:passwd|password|key|group-password|auth-password-l1|auth-password-l2|rsso|history0|history1)) .+", "<removed>"]]'
        }
    )

    sample = """
    edit "WCG_Admin"
        set accprofile "super_admin"
        set password ENC PB2HrXzVLUR4
    next
config system ha
    set password ENC nXWe05bntDXznP2tTUh3+
    set hbdev "port1" 0 "port2" 0
"""
    dyn = create_dynamic_model(cm)
    inst = dyn()
    out = sample
    for f in inst._cmds['all']:
        out = f(inst, out)

    assert "ENC PB2HrXzVLUR4" not in out
    assert "ENC nXWe05bntDXznP2tTUh3+" not in out
    assert "<removed>" in out


@pytest.mark.django_db
def test_device_model_dropdown_shows_only_enabled_models():
    """Verify that Device form dropdown only displays enabled models."""
    from oxidized_web.models import CustomModel
    from oxidized_web.views import UserDeviceForm

    CustomModel.objects.filter(name='model_disabled_test').delete()
    CustomModel.objects.create(name='model_disabled_test', description='Disabled OS', enabled=False)

    form = UserDeviceForm()
    model_choices = [c[0] for c in form.fields['model'].choices]
    assert 'model_disabled_test' not in model_choices


@pytest.mark.django_db
def test_config_revision_deduplication():
    """Verify that identical consecutive backups do not create duplicate NodeRevision entries."""
    from oxidized.output import _save_pg_revision
    from oxidized_web.models import NodeRevision

    node = 'dedup-test-device'
    NodeRevision.objects.filter(node_name=node).delete()

    oid1 = _save_pg_revision(node, 'default', 'version 1 content')
    assert NodeRevision.objects.filter(node_name=node).count() == 1

    oid2 = _save_pg_revision(node, 'default', 'version 1 content')
    assert NodeRevision.objects.filter(node_name=node).count() == 1
    assert oid1 == oid2

    oid3 = _save_pg_revision(node, 'default', 'version 2 content')
    assert NodeRevision.objects.filter(node_name=node).count() == 2
    assert oid3 != oid1
