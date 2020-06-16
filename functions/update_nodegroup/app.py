import boto3
import json
import os
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def create_eks_client():
    return boto3.client('eks')

def lambda_handler(event, context):
    logger.info(event)

    cluster_name = event.get('cluster_name')
    nodegroup = event.get('nodegroup')

    eks_client = create_eks_client()

    res = eks_client.update_nodegroup_version(
        clusterName=cluster_name,
        nodegroupName=nodegroup,
    )

    logger.info(f'update started: {res["update"]["id"]}')

    return res['update']['id']
