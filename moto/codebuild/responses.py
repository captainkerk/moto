from __future__ import unicode_literal

from moto.core.responses import BaseResponse
from moto.core.utils import amz_crc32, amzn_request_id
from .models import codebuild_backends

class CodebuildResponse(BaseResponse):

    @property
    def codebuild_backend(self):
        return codebuild_backends[self.region]


    def create_project(self):
        project = self.codebuild_backend.create_project(
            name=self._get_param('ProjectName'),
            source=self._get_param('Source'),
            artifacts=self._get_param('Artifacts'),
            environment=self._get_param('Environment')
        )
        template = self.response_template(CREATE_PROJECT_TEMPLATE)
        return template.render()



CREATE_PROJECT_TEMPLATE = """<CreateProjectResponse xmlns="http://codebuild.amazonaws.com/doc/2011-01-01/">
<ResponseMetadata>
   <RequestId>7c6e177f-f082-11e1-ac58-3714bEXAMPLE</RequestId>
</ResponseMetadata>
</CreateProjectResponse>"""
