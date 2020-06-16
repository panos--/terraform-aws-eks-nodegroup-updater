import pytest
import botocore.session
from botocore.stub import Stubber

import boto3
from functions.update_nodegroup import app

@pytest.mark.parametrize(
    'cluster_name,nodegroup,expected_result',
    [
        ('cluster1', 'nodegroup1', '123456'),
        ('cluster2', 'nodegroup2', 'foobar'),
    ]
)
def test_lambda_handler(mocker, eks_stub, cluster_name, nodegroup, expected_result):
    mock = mocker.patch('functions.update_nodegroup.app.create_eks_client', autospec=True)
    mock.side_effect = lambda : eks_stub.client

    expected_params = { 'clusterName': cluster_name, 'nodegroupName': nodegroup }
    response = { 'update': { 'id': expected_result } }
    eks_stub.add_response('update_nodegroup_version', response, expected_params)

    update_id = app.lambda_handler({ 'cluster_name': cluster_name, 'nodegroup': nodegroup }, {})
    
    assert update_id == expected_result
