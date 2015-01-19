from __future__ import unicode_literals

import copy

import boto.rds2
from jinja2 import Template

from moto.cloudformation.exceptions import UnformattedGetAttTemplateException
from moto.core import BaseBackend
from moto.core.utils import get_random_hex
from moto.ec2.models import ec2_backends
from .exceptions import RDSClientError, DBInstanceNotFoundError, DBSecurityGroupNotFoundError, DBSubnetGroupNotFoundError


class Database(object):
    def __init__(self, **kwargs):
        self.status = "available"
        self.is_replica = False
        self.replicas = []
        self.region = kwargs.get('region')
        self.engine = kwargs.get("engine")
        self.engine_version = kwargs.get("engine_version", None)
        self.default_engine_versions = {"MySQL": "5.6.21",
                                        "mysql": "5.6.21",
                                        "oracle-se1": "11.2.0.4.v3",
                                        "oracle-se": "11.2.0.4.v3",
                                        "oracle-ee": "11.2.0.4.v3",
                                        "sqlserver-ee": "11.00.2100.60.v1",
                                        "sqlserver-se": "11.00.2100.60.v1",
                                        "sqlserver-ex": "11.00.2100.60.v1",
                                        "sqlserver-web": "11.00.2100.60.v1",
                                        "postgres": "9.3.3"
                                        }
        if not self.engine_version and self.engine in self.default_engine_versions:
            self.engine_version = self.default_engine_versions[self.engine]
        self.iops = kwargs.get("iops")
        self.storage_type = kwargs.get("storage_type")
        self.master_username = kwargs.get('master_username')
        self.master_user_password = kwargs.get('master_user_password')
        self.auto_minor_version_upgrade = kwargs.get('auto_minor_version_upgrade')
        if self.auto_minor_version_upgrade is None:
            self.auto_minor_version_upgrade = True
        self.allocated_storage = kwargs.get('allocated_storage')
        self.db_instance_identifier = kwargs.get('db_instance_identifier')
        self.source_db_identifier = kwargs.get("source_db_identifier")
        self.db_instance_class = kwargs.get('db_instance_class')
        self.port = kwargs.get('port')
        self.db_instance_identifier = kwargs.get('db_instance_identifier')
        self.db_name = kwargs.get("db_name")
        self.publicly_accessible = kwargs.get("publicly_accessible")
        if self.publicly_accessible is None:
            self.publicly_accessible = True
        self.backup_retention_period = kwargs.get("backup_retention_period")
        if self.backup_retention_period is None:
            self.backup_retention_period = 1
        self.availability_zone = kwargs.get("availability_zone")
        self.multi_az = kwargs.get("multi_az")
        self.db_subnet_group_name = kwargs.get("db_subnet_group_name")
        if self.db_subnet_group_name:
            self.db_subnet_group = rds2_backends[self.region].describe_subnet_groups(self.db_subnet_group_name)[0]
        else:
            self.db_subnet_group = []
        self.db_security_groups = kwargs.get('security_groups', ['a'])
        self.vpc_security_group_ids = kwargs.get('vpc_security_group_ids', [])
        self.preferred_maintenance_window = kwargs.get('preferred_maintenance_window', 'wed:06:38-wed:07:08')
        self.db_parameter_group_name = kwargs.get('db_parameter_group_name', None)
        self.default_parameter_groups = {"MySQL": "default.mysql5.6",
                                         "mysql": "default.mysql5.6",
                                         "postgres": "default.postgres9.3"
                                         }
        if not self.db_parameter_group_name and self.engine in self.default_parameter_groups:
            self.db_parameter_group_name = self.default_parameter_groups[self.engine]

        self.preferred_backup_window = kwargs.get('preferred_backup_window', '13:14-13:44')
        self.license_model = kwargs.get('license_model', 'general-public-license')
        self.option_group_name = kwargs.get('option_group_name', None)
        self.default_option_groups = {"MySQL": "default.mysql5.6",
                                      "mysql": "default.mysql5.6",
                                      "postgres": "default.postgres9.3"
                                      }
        if not self.option_group_name and self.engine in self.default_option_groups:
            self.option_group_name = self.default_option_groups[self.engine]
        self.character_set_name = kwargs.get('character_set_name', None)
        self.tags = kwargs.get('tags', None)

    @property
    def address(self):
        return "{0}.aaaaaaaaaa.{1}.rds.amazonaws.com".format(self.db_instance_identifier, self.region)

    def add_replica(self, replica):
        self.replicas.append(replica.db_instance_identifier)

    def remove_replica(self, replica):
        self.replicas.remove(replica.db_instance_identifier)

    def set_as_replica(self):
        self.is_replica = True
        self.replicas = []

    def update(self, db_kwargs):
        for key, value in db_kwargs.items():
            if value is not None:
                setattr(self, key, value)

    def get_cfn_attribute(self, attribute_name):
        if attribute_name == 'Endpoint.Address':
            return self.address
        elif attribute_name == 'Endpoint.Port':
            return self.port
        raise UnformattedGetAttTemplateException()

    @classmethod
    def create_from_cloudformation_json(cls, resource_name, cloudformation_json, region_name):
        properties = cloudformation_json['Properties']

        db_instance_identifier = properties.get('DBInstanceIdentifier')
        if not db_instance_identifier:
            db_instance_identifier = resource_name.lower() + get_random_hex(12)
        db_security_groups = properties.get('DBSecurityGroups')
        if not db_security_groups:
            db_security_groups = []
        security_groups = [group.group_name for group in db_security_groups]
        db_subnet_group = properties.get("DBSubnetGroupName")
        db_subnet_group_name = db_subnet_group.subnet_name if db_subnet_group else None
        db_kwargs = {
            "auto_minor_version_upgrade": properties.get('AutoMinorVersionUpgrade'),
            "allocated_storage": properties.get('AllocatedStorage'),
            "availability_zone": properties.get("AvailabilityZone"),
            "backup_retention_period": properties.get("BackupRetentionPeriod"),
            "db_instance_class": properties.get('DBInstanceClass'),
            "db_instance_identifier": db_instance_identifier,
            "db_name": properties.get("DBName"),
            "db_subnet_group_name": db_subnet_group_name,
            "engine": properties.get("Engine"),
            "engine_version": properties.get("EngineVersion"),
            "iops": properties.get("Iops"),
            "master_password": properties.get('MasterUserPassword'),
            "master_username": properties.get('MasterUsername'),
            "multi_az": properties.get("MultiAZ"),
            "port": properties.get('Port', 3306),
            "publicly_accessible": properties.get("PubliclyAccessible"),
            "region": region_name,
            "security_groups": security_groups,
            "storage_type": properties.get("StorageType"),
        }

        rds2_backend = rds2_backends[region_name]
        source_db_identifier = properties.get("SourceDBInstanceIdentifier")
        if source_db_identifier:
            # Replica
            db_kwargs["source_db_identifier"] = source_db_identifier.db_instance_identifier
            database = rds2_backend.create_database_replica(db_kwargs)
        else:
            database = rds2_backend.create_database(db_kwargs)
        return database

    def to_json(self):
        template = Template(""""DBInstance": {
        "AllocatedStorage": 10,
        "AutoMinorVersionUpgrade": "{{ database.auto_minor_version_upgrade }}",
        "AvailabilityZone": "{{ database.availability_zone }}",
        "BackupRetentionPeriod": "{{ database.backup_retention_period }}",
        "CharacterSetName": {%- if database.character_set_name -%}{{ database.character_set_name }}{%- else %} null{%- endif -%},
        "DBInstanceClass": "{{ database.db_instance_class }}",
        "DBInstanceIdentifier": "{{ database.db_instance_identifier }}",
        "DBInstanceStatus": "{{ database.status }}",
        "DBName": {%- if database.db_name -%}{{ database.db_name }}{%- else %} null{%- endif -%},
        {% if database.db_parameter_group_name -%}"DBParameterGroups": {
            "DBParameterGroup": {
            "ParameterApplyStatus": "in-sync",
            "DBParameterGroupName": "{{ database.db_parameter_group_name }}"
          }
        },{%- endif %}
        "DBSecurityGroups": [{
          {% for security_group in database.db_security_groups -%}{%- if loop.index != 1 -%},{%- endif -%}
          "DBSecurityGroup": {
            "Status": "active",
            "DBSecurityGroupName": "{{ security_group }}"
          }{% endfor %}
        }],{%- if database.db_subnet_group -%}
        "DBSubnetGroup": {
            "DBSubnetGroupDescription": "nabil-db-subnet-group",
            "DBSubnetGroupName": "nabil-db-subnet-group",
            "SubnetGroupStatus": "Complete",
            "Subnets": [
                {
                    "SubnetAvailabilityZone": {
                        "Name": "us-west-2c",
                        "ProvisionedIopsCapable": false
                    },
                    "SubnetIdentifier": "subnet-c0ea0099",
                    "SubnetStatus": "Active"
                },
                {
                    "SubnetAvailabilityZone": {
                        "Name": "us-west-2a",
                        "ProvisionedIopsCapable": false
                    },
                    "SubnetIdentifier": "subnet-ff885d88",
                    "SubnetStatus": "Active"
                }
            ],
            "VpcId": "vpc-8e6ab6eb"
        },{%- endif %}
        "Engine": "{{ database.engine }}",
        "EngineVersion": "{{ database.engine_version }}",
        "LatestRestorableTime": null,
        "LicenseModel": "{{ database.license_model }}",
        "MasterUsername": "{{ database.master_username }}",
        "MultiAZ": "{{ database.multi_az }}",{% if database.option_group_name %}
        "OptionGroupMemberships": [{
          "OptionGroupMembership": {
            "OptionGroupName": "{{ database.option_group_name }}",
            "Status": "in-sync"
          }
        }],{%- endif %}
        "PendingModifiedValues": { "MasterUserPassword": "****" },
        "PreferredBackupWindow": "{{ database.preferred_backup_window }}",
        "PreferredMaintenanceWindow": "{{ database.preferred_maintenance_window }}",
        "PubliclyAccessible": "{{ database.publicly_accessible }}",
        "AllocatedStorage": "{{ database.allocated_storage }}",
        "Endpoint": null,
        "InstanceCreateTime": null,
        "Iops": null,
        "ReadReplicaDBInstanceIdentifiers": [],
        "ReadReplicaSourceDBInstanceIdentifier": null,
        "SecondaryAvailabilityZone": null,
        "StatusInfos": null,
        "VpcSecurityGroups": [
            {
                "Status": "active",
                "VpcSecurityGroupId": "sg-123456"
            }
        ]
      }""")
        return template.render(database=self)


class SecurityGroup(object):
    def __init__(self, group_name, description):
        self.group_name = group_name
        self.description = description
        self.status = "authorized"
        self.ip_ranges = []
        self.ec2_security_groups = []

    def to_xml(self):
        template = Template("""<DBSecurityGroup>
            <EC2SecurityGroups>
            {% for security_group in security_group.ec2_security_groups %}
                <EC2SecurityGroup>
                    <EC2SecurityGroupId>{{ security_group.id }}</EC2SecurityGroupId>
                    <EC2SecurityGroupName>{{ security_group.name }}</EC2SecurityGroupName>
                    <EC2SecurityGroupOwnerId>{{ security_group.owner_id }}</EC2SecurityGroupOwnerId>
                    <Status>authorized</Status>
                </EC2SecurityGroup>
            {% endfor %}
            </EC2SecurityGroups>

            <DBSecurityGroupDescription>{{ security_group.description }}</DBSecurityGroupDescription>
            <IPRanges>
            {% for ip_range in security_group.ip_ranges %}
                <IPRange>
                    <CIDRIP>{{ ip_range }}</CIDRIP>
                    <Status>authorized</Status>
                </IPRange>
            {% endfor %}
            </IPRanges>
            <OwnerId>{{ security_group.ownder_id }}</OwnerId>
            <DBSecurityGroupName>{{ security_group.group_name }}</DBSecurityGroupName>
        </DBSecurityGroup>""")
        return template.render(security_group=self)

    def authorize_cidr(self, cidr_ip):
        self.ip_ranges.append(cidr_ip)

    def authorize_security_group(self, security_group):
        self.ec2_security_groups.append(security_group)

    @classmethod
    def create_from_cloudformation_json(cls, resource_name, cloudformation_json, region_name):
        properties = cloudformation_json['Properties']
        group_name = resource_name.lower() + get_random_hex(12)
        description = properties['GroupDescription']
        security_group_ingress = properties['DBSecurityGroupIngress']

        ec2_backend = ec2_backends[region_name]
        rds2_backend = rds2_backends[region_name]
        security_group = rds2_backend.create_security_group(
            group_name,
            description,
        )
        for ingress_type, ingress_value in security_group_ingress.items():
            if ingress_type == "CIDRIP":
                security_group.authorize_cidr(ingress_value)
            elif ingress_type == "EC2SecurityGroupName":
                subnet = ec2_backend.get_security_group_from_name(ingress_value)
                security_group.authorize_security_group(subnet)
            elif ingress_type == "EC2SecurityGroupId":
                subnet = ec2_backend.get_security_group_from_id(ingress_value)
                security_group.authorize_security_group(subnet)
        return security_group


class SubnetGroup(object):
    def __init__(self, subnet_name, description, subnets):
        self.subnet_name = subnet_name
        self.description = description
        self.subnets = subnets
        self.status = "Complete"

        self.vpc_id = self.subnets[0].vpc_id

    def to_xml(self):
        template = Template("""<DBSubnetGroup>
              <VpcId>{{ subnet_group.vpc_id }}</VpcId>
              <SubnetGroupStatus>{{ subnet_group.status }}</SubnetGroupStatus>
              <DBSubnetGroupDescription>{{ subnet_group.description }}</DBSubnetGroupDescription>
              <DBSubnetGroupName>{{ subnet_group.subnet_name }}</DBSubnetGroupName>
              <Subnets>
                {% for subnet in subnet_group.subnets %}
                <Subnet>
                  <SubnetStatus>Active</SubnetStatus>
                  <SubnetIdentifier>{{ subnet.id }}</SubnetIdentifier>
                  <SubnetAvailabilityZone>
                    <Name>{{ subnet.availability_zone }}</Name>
                    <ProvisionedIopsCapable>false</ProvisionedIopsCapable>
                  </SubnetAvailabilityZone>
                </Subnet>
                {% endfor %}
              </Subnets>
            </DBSubnetGroup>""")
        return template.render(subnet_group=self)

    @classmethod
    def create_from_cloudformation_json(cls, resource_name, cloudformation_json, region_name):
        properties = cloudformation_json['Properties']

        subnet_name = resource_name.lower() + get_random_hex(12)
        description = properties['DBSubnetGroupDescription']
        subnet_ids = properties['SubnetIds']

        ec2_backend = ec2_backends[region_name]
        subnets = [ec2_backend.get_subnet(subnet_id) for subnet_id in subnet_ids]
        rds2_backend = rds2_backends[region_name]
        subnet_group = rds2_backend.create_subnet_group(
            subnet_name,
            description,
            subnets,
        )
        return subnet_group


class RDS2Backend(BaseBackend):

    def __init__(self):
        self.databases = {}
        self.security_groups = {}
        self.subnet_groups = {}
        self.option_groups = {}

    def create_database(self, db_kwargs):
        database_id = db_kwargs['db_instance_identifier']
        database = Database(**db_kwargs)
        self.databases[database_id] = database
        return database

    def create_database_replica(self, db_kwargs):
        database_id = db_kwargs['db_instance_identifier']
        source_database_id = db_kwargs['source_db_identifier']
        primary = self.describe_databases(source_database_id)[0]
        replica = copy.deepcopy(primary)
        replica.update(db_kwargs)
        replica.set_as_replica()
        self.databases[database_id] = replica
        primary.add_replica(replica)
        return replica

    def describe_databases(self, db_instance_identifier=None):
        if db_instance_identifier:
            if db_instance_identifier in self.databases:
                return [self.databases[db_instance_identifier]]
            else:
                raise DBInstanceNotFoundError(db_instance_identifier)
        return self.databases.values()

    def modify_database(self, db_instance_identifier, db_kwargs):
        database = self.describe_databases(db_instance_identifier)[0]
        database.update(db_kwargs)
        return database

    def delete_database(self, db_instance_identifier):
        if db_instance_identifier in self.databases:
            database = self.databases.pop(db_instance_identifier)
            if database.is_replica:
                primary = self.describe_databases(database.source_db_identifier)[0]
                primary.remove_replica(database)
            return database
        else:
            raise DBInstanceNotFoundError(db_instance_identifier)

    def create_security_group(self, group_name, description):
        security_group = SecurityGroup(group_name, description)
        self.security_groups[group_name] = security_group
        return security_group

    def describe_security_groups(self, security_group_name):
        if security_group_name:
            if security_group_name in self.security_groups:
                return [self.security_groups[security_group_name]]
            else:
                raise DBSecurityGroupNotFoundError(security_group_name)
        return self.security_groups.values()

    def delete_security_group(self, security_group_name):
        if security_group_name in self.security_groups:
            return self.security_groups.pop(security_group_name)
        else:
            raise DBSecurityGroupNotFoundError(security_group_name)

    def authorize_security_group(self, security_group_name, cidr_ip):
        security_group = self.describe_security_groups(security_group_name)[0]
        security_group.authorize_cidr(cidr_ip)
        return security_group

    def create_subnet_group(self, subnet_name, description, subnets):
        subnet_group = SubnetGroup(subnet_name, description, subnets)
        self.subnet_groups[subnet_name] = subnet_group
        return subnet_group

    def describe_subnet_groups(self, subnet_group_name):
        if subnet_group_name:
            if subnet_group_name in self.subnet_groups:
                return [self.subnet_groups[subnet_group_name]]
            else:
                raise DBSubnetGroupNotFoundError(subnet_group_name)
        return self.subnet_groups.values()

    def delete_subnet_group(self, subnet_name):
        if subnet_name in self.subnet_groups:
            return self.subnet_groups.pop(subnet_name)
        else:
            raise DBSubnetGroupNotFoundError(subnet_name)

    def create_option_group(self, option_group_kwargs):
        option_group_id = option_group_kwargs['name']
        valid_option_group_engines = {'postgres': ['9.3'], 'mysql': []}

        if 'description' not in option_group_kwargs or not option_group_kwargs['description']:
            raise RDSClientError('InvalidParameterValue',
                                 'The parameter OptionGroupDescription must be provided and must not be blank.')
        if option_group_kwargs['engine_name'] not in valid_option_group_engines.keys():
            raise RDSClientError('InvalidParameterValue', 'Invalid DB engine: non-existant')
        if option_group_kwargs['major_engine_version'] not in\
           valid_option_group_engines[option_group_kwargs['engine_name']]:
                raise RDSClientError('InvalidParameterCombination',
                                     'Cannot find major version {0} for {1}'.format(
                                         option_group_kwargs['major_engine_version'],
                                         option_group_kwargs['engine_name']
                                     ))
        option_group = OptionGroup(**option_group_kwargs)
        self.option_groups[option_group_id] = option_group
        return option_group


class OptionGroup(object):
    def __init__(self, name, engine_name, major_engine_version, description=None):
        self.engine_name = engine_name
        self.major_engine_version = major_engine_version
        self.description = description
        self.name = name
        self.vpc_and_non_vpc_instance_memberships = False
        self.options = {}
        self.vpcId = 'null'

    def to_json(self):
        template = Template("""{
    "VpcId": null,
    "MajorEngineVersion": "{{ option_group.major_engine_version }}",
    "OptionGroupDescription": "{{ option_group.description }}",
    "AllowsVpcAndNonVpcInstanceMemberships": "{{ option_group.vpc_and_non_vpc_instance_memberships }}",
    "EngineName": "{{ option_group.engine_name }}",
    "Options": [],
    "OptionGroupName": "{{ option_group.name }}"
}""")
        return template.render(option_group=self)

rds2_backends = {}
for region in boto.rds2.regions():
    rds2_backends[region.name] = RDS2Backend()
