import pytest
import botocore.session
from botocore.stub import Stubber

@pytest.fixture
def ssm_stub():
    with Stubber(botocore.session.get_session().create_client('ssm')) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()

@pytest.fixture
def eks_stub():
    with Stubber(botocore.session.get_session().create_client('eks')) as stubber:
        yield stubber
        stubber.assert_no_pending_responses()
