import pytest
from oxidized.config import Config, ConfigDict
from oxidized.node import Node
from oxidized.nodes import Nodes
from oxidized.model import resolve_model
from oxidized.model.models import IOS, JunOS, EOS
from oxidized.input import MockInput
from oxidized.output import FileOutput, GitOutput
from oxidized_web.models import OxidizedSetting, RouterDbEntry, Device
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
        config_yaml="""
threads: 42
username: testuser
password: secretpassword
"""
    )
    cfg = Config.load()
    assert cfg.threads == 42
    assert cfg.username == 'testuser'
    assert cfg.password == 'secretpassword'

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
