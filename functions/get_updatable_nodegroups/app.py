import boto3
import json
import os
import logging
import re

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def version_string_to_array(s):
    return re.split(r'[\.-]', s)

def compare_version(a, b):
    aa = version_string_to_array(a)
    ba = version_string_to_array(b)

    if len(aa) != len(ba):
        raise f'Unequal number of version number components: {a} vs. {b}'

    for ac, bc in zip(aa, ba):
        an = int(ac)
        bn = int(bc)
        if an > bn:
            return 1
        elif an < bn:
            return -1

    return 0

class SSMClient:
    def __init__(self, client=None) -> None:
        if client is None:
            self.client = boto3.client('ssm')
        else:
            self.client = client
    
    def get_parameter(self, name):
        return self.client.get_parameter(Name=name)

class EKSClient:
    def __init__(self, ssm_client, eks_client=None) -> None:
        if eks_client is None:
            self.client = boto3.client('eks')
        else:
            self.client = eks_client
        self.ssm_client = ssm_client

    def get_cluster_version(self, cluster_name):
        res = self.client.describe_cluster(name=cluster_name)
        return res['cluster']['version']

    def get_latest_node_version(self, cluster_version):
        res = self.ssm_client.get_parameter(
            f'/aws/service/eks/optimized-ami/{cluster_version}/amazon-linux-2/recommended/release_version')
        return res['Parameter']['Value']

    def get_nodegroups(self, cluster_name):
        res = self.client.list_nodegroups(clusterName=cluster_name, maxResults=100)
        return res['nodegroups']

    def get_nodegroup_version(self, cluster_name, nodegroup):
        res = self.client.describe_nodegroup(clusterName=cluster_name, nodegroupName=nodegroup)
        return res['nodegroup']['releaseVersion']

def get_updatable_nodegroups(eks_client, cluster_name):
    cluster_version = eks_client.get_cluster_version(cluster_name)
    logger.info(f'cluster version: {cluster_version}')

    latest_node_version = eks_client.get_latest_node_version(cluster_version)    
    logger.info(f'recommended nodegroup version: {latest_node_version}')

    nodegroups = eks_client.get_nodegroups(cluster_name)

    updatable_nodegroups = []
    for nodegroup in nodegroups:
        current_node_version = eks_client.get_nodegroup_version(cluster_name, nodegroup)
        logger.info(f'nodegroup {nodegroup} version: {current_node_version}')

        if compare_version(latest_node_version, current_node_version) > 0:
            logger.info(f'nodegroup {nodegroup} needs update')
            updatable_nodegroups.append(nodegroup)

    logger.info(f'updatable nodegroups: {updatable_nodegroups}')
    return updatable_nodegroups

def create_ssm_client():
    return SSMClient()

def create_eks_client(ssm_client):
    return EKSClient(ssm_client)

def lambda_handler(event, context):
    logger.info(event)
    ssm_client = create_ssm_client()
    eks_client = create_eks_client(ssm_client)
    return get_updatable_nodegroups(eks_client, event.get('cluster_name'))
