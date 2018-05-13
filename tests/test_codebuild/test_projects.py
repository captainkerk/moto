from __future__ import unicode_literals
import boto
import boto3
import sure  # noqa

from moto import mock_codebuild
from tests.helpers import requires_boto_gte

from utils import setup_networking, setup_networking_deprecated


@mock_codebuild
def test_create_codebuild():
    conn = boto3.client('codebuild', region_name='us-east-1')
    import ipdb; ipdb.set_trace()

    resp = conn.create_project(
        name='first-step',
        source={},
        artifacts={},
        environment={},
    )
    print(resp)


