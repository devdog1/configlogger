import pytest
from oxidized.config import Config, ConfigDict
from oxidized.node import Node
from oxidized.nodes import Nodes
from oxidized.model import resolve_model
from oxidized.model.models import IOS, JunOS, EOS
from oxidized.input import MockInput
from oxidized.output import FileOutput, GitOutput
from oxidized_web.models import OxidizedSetting, RouterDbEntry, Device, CustomModel
import tempfile
import shutil

@pytest.mark.django_db
def test_config_dict():
    cfg = ConfigDict({'threads': 10, 'nested': {'value': 'hello'}})
    assert cfg.threads == 10
    assert cfg.nested.value == 'hello'
    assert cfg.get_path('nested.value') == 'hello'
    assert cfg.get_path('non.existent', 'default') == 'default'

@pytest.mark.django_db
def test_oxidized_setting_postgres_load():
    OxidizedSetting.objects.all().delete()
    OxidizedSetting.objects.create(
        key='main',
        threads=200,
        username='adminuser',
        password='secretpassword',
        interval=43200,
        timeout=300,
        retries=1,
        debug=True,
        use_syslog=True,
        model_overrides={'routeros': {'username': 'ros_user', 'password': 'ros_password'}}
    )
    cfg = Config.load()
    assert cfg.threads == 200
    assert cfg.username == 'adminuser'
    assert cfg.password == 'secretpassword'
    assert cfg.interval == 43200
    assert cfg.timeout == 300
    assert cfg.retries == 1
    assert cfg.debug is True
    assert cfg.use_syslog is True
    assert cfg.models['routeros']['username'] == 'ros_user'

@pytest.mark.django_db
def test_router_db_and_device_sources():
    RouterDbEntry.objects.all().delete()
    RouterDbEntry.objects.create(
        name='router.db',
        content='r-csv1:ios:default\nr-csv2:junos:edge\n'
    )
    Device.objects.all().delete()
    Device.objects.create(
        name='sw-db1',
        ip='192.168.1.1',
        model='eos',
        group='switches',
        input_type='mock'
    )

    nodes = Nodes()
    names = [n.name for n in nodes]
    assert 'r-csv1' in names
    assert 'r-csv2' in names
    assert 'sw-db1' in names

    sw_node = nodes.get('sw-db1')
    assert sw_node.ip == '192.168.1.1'
    assert sw_node.model_name == 'eos'
    assert sw_node.group == 'switches'

@pytest.mark.django_db
def test_custom_model_from_database():
    CustomModel.objects.filter(name='vyos').delete()
    cm = CustomModel.objects.create(
        name='vyos',
        description='VyOS Router platform',
        prompt_regex=r'^[\w.-]+@[\w.-]+:.*[#$]\s?$',
        comment_prefix='# ',
        commands=['show version', 'show configuration commands'],
        clean_filters=[[r'password \S+', 'password <secret hidden>']]
    )

    resolved_cls = resolve_model('vyos')
    assert resolved_cls is not None
    assert resolved_cls._comment == '# '

    # Test executing node with custom model
    node = Node({
        'name': 'vyos-gw',
        'ip': '192.168.10.1',
        'model': 'vyos',
        'input': 'mock',
        'output': 'file',
        'vars': {'remove_secret': True}
    })
    success = node.run()
    assert success is True
    assert node.last['status'] == 'success'

@pytest.mark.django_db
def test_model_execution_and_output():
    tmp_dir = tempfile.mkdtemp()
    try:
        node_data = {
            'name': 'test-ios-node',
            'ip': '127.0.0.1',
            'model': 'ios',
            'group': 'core',
            'input': 'mock',
            'output': 'file'
        }
        node = Node(node_data)
        node.output = FileOutput({'directory': tmp_dir})
        success = node.run()
        assert success is True
        assert node.last['status'] == 'success'

        content = node.output.fetch('test-ios-node', group='core')
        assert content is not None
        assert 'test-ios-node' in content
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

@pytest.mark.django_db
def test_git_output_versions_and_diff():
    tmp_git = tempfile.mkdtemp()
    try:
        git_out = GitOutput({'repo': tmp_git, 'user': 'Tester', 'email': 't@example.com'})
        git_out.store('switch1', "version 1\ninterface GigabitEthernet0/1\n")
        git_out.store('switch1', "version 2\ninterface GigabitEthernet0/1\n  no shutdown\n")

        versions = git_out.version('switch1')
        assert len(versions) == 2

        oid1 = versions[1]['oid']
        oid2 = versions[0]['oid']
        diff = git_out.get_diff('switch1', oid1=oid1, oid2=oid2)
        assert '+  no shutdown' in diff
    finally:
        shutil.rmtree(tmp_git, ignore_errors=True)

def test_all_supported_os_types_resolve():
    import re
    from oxidized.model import resolve_model
    from oxidized.model.models import IOS

    # Read Supported-OS-Types.md
    with open('docs/Supported-OS-Types.md', 'r') as f:
        content = f.read()

    doc_models = set(m.group(2) for m in re.finditer(r'\[([a-zA-Z0-9_-]+)\]\(/lib/oxidized/model/([a-zA-Z0-9_-]+)\.rb\)', content))
    assert len(doc_models) >= 190, f"Expected at least 190 models in doc, got {len(doc_models)}"

    resolved_count = 0
    for model_name in doc_models:
        cls = resolve_model(model_name)
        assert cls is not None
        assert cls != IOS or model_name in ('ios', 'cisco')
        assert hasattr(cls, '_prompt')
        assert hasattr(cls, '_comment')
        assert hasattr(cls, '_cmds')
        resolved_count += 1

    assert resolved_count == len(doc_models)

def test_legacy_ssh_algorithms_registered():
    from paramiko.transport import Transport
    import oxidized.input
    assert 'diffie-hellman-group-exchange-sha1' in Transport._preferred_kex
    assert 'diffie-hellman-group14-sha1' in Transport._preferred_kex
    assert 'diffie-hellman-group1-sha1' in Transport._preferred_kex
    assert 'ssh-rsa' in Transport._preferred_keys

@pytest.mark.django_db
def test_postgresql_node_revision_storage():
    from oxidized.output import DatabaseOutput, _save_pg_revision, _get_pg_versions, _get_pg_diff
    from oxidized_web.models import NodeRevision

    oid1 = _save_pg_revision("test-db-node", "default", "hostname test-db-node\ninterface Gi0/0\n")
    assert oid1 is not None
    oid2 = _save_pg_revision("test-db-node", "default", "hostname test-db-node\ninterface Gi0/0\n ip address 172.16.0.1 255.255.0.0\n")
    assert oid2 is not None

    versions = _get_pg_versions("test-db-node", "default")
    assert len(versions) >= 2
    assert versions[0]['oid'] == oid2

    diff = _get_pg_diff("test-db-node", "default", oid1, oid2)
    assert "+ ip address 172.16.0.1" in diff

@pytest.mark.django_db
def test_ssh_crypto_options_and_transport():
    from oxidized.input import SSHInput
    node_data = {
        'name': 'test-crypto-node',
        'ip': '127.0.0.1',
        'model': 'ios',
        'group': 'core',
        'input': 'ssh',
        'output': 'db',
        'ssh_kex': '+diffie-hellman-group14-sha1',
        'ssh_hostkey': '+ssh-rsa',
        'ssh_ciphers': '+aes128-cbc',
        'ssh_clear_hostkey': True,
        'vars': {
            'ssh_kex': '+diffie-hellman-group14-sha1',
            'ssh_hostkey': '+ssh-rsa',
            'ssh_ciphers': '+aes128-cbc',
            'ssh_clear_hostkey': True
        }
    }
    node = Node(node_data)
    d = node.to_dict()
    assert d['ssh_kex'] == '+diffie-hellman-group14-sha1'
    assert d['ssh_hostkey'] == '+ssh-rsa'
    assert d['ssh_ciphers'] == '+aes128-cbc'
    assert d['input_driver'] == 'ssh'
    assert d['model'] == 'ios'
    assert d['timeout'] == node.timeout
    assert d['retries'] == node.retries
