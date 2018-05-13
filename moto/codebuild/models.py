from __future__ import unicode_literals
from collections import OrderedDict
import boto.ec2
import uuid
import time


from moto.core import BaseBackend, BaseModel


class Project(BaseModel):

    def __init__(self, name, source, artifacts, environment, codebuild_backend, **kwargs):

        self.name = name
        self.source = source
        self.artifacts = artifacts
        self.environment = environment


class Build(BaseModel):

    def __init__(self, project_name, codebuild_backend, **kwargs):

        self.codebuild_backend = codebuild_backend
        self.project = codebuild_backend.projects[project_name].source
        self.project_name = project_name
        self.id = '{0}:{1}'.format(project_name, str(uuid.uuid4()))
        self.start_time = time.time()
        self.end_time = ''
        self.current_phase = ''
        self.build_status = 'IN_PROGRESS'
        self.source_version = kwargs.get('source_version', 'HEAD')
        self.phases = []
        self.source = self.project.source
        self.artifacts = self.project.artifact
        self.cache = self.project.cache



class CodebuildBackend(BaseBackend):

    def __init__(self):
        self.projects = OrderedDict()
        self.runs = OrderedDict()

    def create_project(self, name, source, artifacts, environment):
        project = Project(name, source, artifacts, environment, codebuild_backend=self)
        self.projects[name] = project
        return project

    def list_projects(self):
        return self.projects.values()

codebuild_backends = {}
for region in boto.ec2.regions():
    codebuild_backends[region.name] = CodebuildBackend()
