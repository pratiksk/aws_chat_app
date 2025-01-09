def lambda_handler(event, context):
    connection_id = event['requestContext']['connectionId']
    
    # Fetch username before deleting
    response = dynamodb.get_item(
        TableName=os.environ['WEBSOCKET_TABLE'],
        Key={'connectionId': {'S': connection_id}}
    )
    username = response.get('Item', {}).get('username', {}).get('S', 'Unknown User')
    
    # Broadcast disconnection message
    broadcast_message(f"{username} has left the chat.", event)
    
    # Delete connectionId
    dynamodb.delete_item(
        TableName=os.environ['WEBSOCKET_TABLE'],
        Key={'connectionId': {'S': connection_id}}
    )
    
    return {}
