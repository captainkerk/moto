from __future__ import unicode_literals
from .models import codebuild_backends
from ..core.models import base_decorator

codebuild_backend = codebuild_backends['us-east-1']
mock_codebuild = base_decorator(codebuild_backends)
