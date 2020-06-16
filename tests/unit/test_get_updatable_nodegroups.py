import pytest
import botocore.session
from botocore.stub import Stubber

import boto3
from functions.get_updatable_nodegroups import app

@pytest.mark.parametrize(
    'a,b,expected',
    [
        ('1', '0', 1),
        ('1', '1', 0),
        ('0', '1', -1),
        ('1', '2', -1),
        ('2', '10', -1), # test numeric comparison
        ('1.1', '1.0', 1),
        ('1.1', '1.1', 0),
        ('1.0', '1.1', -1),
        ('1.2', '1.10', -1), # test numeric comparison
        ('2.10', '1.10', 1),
        ('1.10.1', '1.10.0', 1),
        ('1.10.1', '1.10.1', 0),
        ('1.10.0', '1.10.1', -1),
        ('1.11.0', '1.10.0', 1),
        ('1.11.2', '1.10.10', 1), # test numeric comparison
        ('1.11.0-1', '1.11.0-0', 1),
        ('1.11.0-1', '1.11.0-1', 0),
        ('1.11.0-0', '1.11.0-1', -1),
        ('1.11.0-2', '1.11.0-10', -1), # test numeric comparison
        ('1.11.1-1', '1.11.0-1', 1),
    ]
)
def test_compare_version(a, b, expected):
    assert app.compare_version(a, b) == expected

@pytest.fixture
def eks_client(ssm_stub, eks_stub):
    eks_client = app.EKSClient(app.SSMClient(ssm_stub.client), eks_stub.client)
    eks_client.ssm_stub = ssm_stub
    eks_client.eks_stub = eks_stub
    return eks_client

class TestEksClient:
    @pytest.mark.parametrize('expected_version', [('1.15'), ('1.16')])
    def test_get_cluster_version(self, eks_client, expected_version):
        expected_params = { 'name': 'test-cluster' }
        response = { 'cluster': { 'version': expected_version } }
        eks_client.eks_stub.add_response('describe_cluster', response, expected_params)

        cluster_version = eks_client.get_cluster_version('test-cluster')
        
        assert cluster_version == expected_version

    @pytest.mark.parametrize('cluster_version', [('1.15'), ('1.16')])
    def test_get_latest_node_version(self, eks_client, cluster_version):
        expected_params = {
            'Name': f'/aws/service/eks/optimized-ami/{cluster_version}/amazon-linux-2/recommended/release_version'
        }
        expected_version = f'{cluster_version}.11-20200520'
        response = { 'Parameter': { 'Value': expected_version } }
        eks_client.ssm_stub.add_response('get_parameter', response, expected_params)
        
        latest_node_version = eks_client.get_latest_node_version(cluster_version)

        assert latest_node_version == expected_version

    @pytest.mark.parametrize(
        'cluster_name,expected_nodegroups',
        [
            ('test-cluster', ['foo', 'bar']),
            ('cluster2', ['anodegroup']),
            ('acluster', []),
        ]
    )
    def test_get_nodegroups(self, eks_client, cluster_name, expected_nodegroups):
        expected_params = { 'clusterName': cluster_name, 'maxResults': 100 }
        response = { 'nodegroups': expected_nodegroups }
        eks_client.eks_stub.add_response('list_nodegroups', response, expected_params)

        nodegroups = eks_client.get_nodegroups(cluster_name)

        assert nodegroups == expected_nodegroups

    @pytest.mark.parametrize(
        'cluster_name,nodegroup,expected_version',
        [
            ('cluster1', 'nodegroup1', '1.15.11-20200520'),
            ('cluster2', 'nodegroup2', '1.16.11-20200520'),
        ]
    )
    def test_get_nodegroup_version(self, eks_client, cluster_name, nodegroup, expected_version):
        expected_params = { 'clusterName': cluster_name, 'nodegroupName': nodegroup }
        response = { 'nodegroup': { 'releaseVersion': expected_version } }
        eks_client.eks_stub.add_response('describe_nodegroup', response, expected_params)

        nodegroup_version = eks_client.get_nodegroup_version(cluster_name, nodegroup)
        
        assert nodegroup_version == expected_version

@pytest.mark.parametrize(
    'cluster_name,cluster_version,latest_nodegroup_version,nodegroups,expected',
    [
        ('test-cluster', '1.15', '1.15.11-20200520', {'foo': '1.15.10-20200401', 'bar': '1.15.10-20200401'}, ['foo', 'bar']),
        ('test-cluster', '1.15', '1.15.11-20200520', {'foo': '1.15.11-20200520', 'bar': '1.15.10-20200401'}, ['bar']),
        ('test-cluster', '1.15', '1.15.11-20200520', {'foo': '1.15.11-20200520', 'bar': '1.15.11-20200520'}, []),
        ('test-cluster', '1.16', '1.16.11-20200520', {'foo': '1.15.11-20200520', 'bar': '1.15.11-20200520'}, ['foo', 'bar']),
    ],
)
def test_get_updatable_nodegroups(mocker, cluster_name, cluster_version, latest_nodegroup_version, nodegroups, expected):
    eks_client = mocker.create_autospec(app.EKSClient)
    eks_client.get_cluster_version.return_value = cluster_version
    eks_client.get_latest_node_version.return_value = latest_nodegroup_version
    eks_client.get_nodegroups.return_value = nodegroups
    eks_client.get_nodegroup_version.side_effect = lambda cluster_name, nodegroup : nodegroups[nodegroup]

    updatable_nodegroups = app.get_updatable_nodegroups(eks_client, cluster_name)

    assert sorted(updatable_nodegroups) == sorted(expected)

@pytest.mark.parametrize('cluster_name', ['cluster1', 'cluster2', 'cluster3'])
def test_lambda_handler(mocker, cluster_name):
    fixture = {
        'cluster1': ['foo', 'bar'],
        'cluster2': ['qux'],
        'cluster3': [],
    }

    mocker.patch('functions.get_updatable_nodegroups.app.create_ssm_client', autospec=True)
    mocker.patch('functions.get_updatable_nodegroups.app.create_eks_client', autospec=True)
    mock = mocker.patch('functions.get_updatable_nodegroups.app.get_updatable_nodegroups', autospec=True)
    mock.side_effect = lambda eks_client, cluster_name : fixture[cluster_name]

    updatable_nodegroups = app.lambda_handler({ 'cluster_name': cluster_name }, {})

    assert updatable_nodegroups == fixture[cluster_name]
