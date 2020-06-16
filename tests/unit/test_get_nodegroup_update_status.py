import pytest
import botocore.session
from botocore.stub import Stubber

import boto3
from datetime import datetime
from functions.get_nodegroup_update_status import app

@pytest.mark.parametrize(
    'cluster_name,nodegroup,update_id,expected_status',
    [
        ('cluster1', 'nodegroup1', '123456', 'InProgress'),
        ('cluster2', 'nodegroup2', 'foobar', 'Success'),
        ('cluster3', 'nodegroup3', 'quxbaz', 'Failure'),
    ]
)
def test_lambda_handler(mocker, eks_stub, cluster_name, nodegroup, update_id, expected_status):
    mock = mocker.patch('functions.get_nodegroup_update_status.app.create_eks_client', autospec=True)
    mock.side_effect = lambda : eks_stub.client

    expected_params = { 'name': cluster_name, 'nodegroupName': nodegroup, 'updateId': update_id }
    response = { 'update': { 'createdAt': datetime.now(), 'status': expected_status } }
    eks_stub.add_response('describe_update', response, expected_params)

    result = app.lambda_handler({
        'cluster_name': cluster_name,
        'nodegroup': nodegroup,
        'update_id': update_id
    }, {})

    expected_result = response['update']
    expected_result['createdAt'] = str(expected_result['createdAt'])
    assert result == expected_result
