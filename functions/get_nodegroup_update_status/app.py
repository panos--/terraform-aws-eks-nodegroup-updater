import boto3
import json
import os
import logging
import random

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def create_eks_client():
    return boto3.client('eks')

def lambda_handler(event, context):
    logger.info(event)

    cluster_name = event.get('cluster_name')
    nodegroup = event.get('nodegroup')
    update_id = event.get('update_id')

    eks_client = create_eks_client()

    res = eks_client.describe_update(
        name=cluster_name,
        nodegroupName=nodegroup,
        updateId=update_id,
    )

    # prevent error "Unable to marshal response: Object of type datetime is not JSON serializable"
    res['update']['createdAt'] = str(res['update']['createdAt'])

    logger.info(f'update status: {res["update"]}')

    return res['update']
