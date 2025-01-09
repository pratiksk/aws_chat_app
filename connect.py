import json
import boto3
import os

dynamodb = boto3.client('dynamodb')

def lambda_handler(event, context):
    connection_id = event['requestContext']['connectionId']
    username = "Anonymous"  # Default username if not registered

    # Save connection details in WEBSOCKET_TABLE
    dynamodb.put_item(
        TableName=os.environ['WEBSOCKET_TABLE'],
        Item={
            'connectionId': {'S': connection_id},
            'username': {'S': username}  # Optional, can be updated later by sendMessage Lambda
        }
    )

    return {
        "statusCode": 200,
        "body": "Connection established"
    }
