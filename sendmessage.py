import json
import boto3
import os
import datetime

dynamodb = boto3.client('dynamodb')

def lambda_handler(event, context):
    body = json.loads(event['body'])
    message = body.get('message', '')
    action_type = body.get('type', '').strip()  # New key for internal logic
    connection_id = event['requestContext']['connectionId']
    connectionIds = []

    # Initialize API Gateway management client
    apigatewaymanagementapi = boto3.client(
        'apigatewaymanagementapi',
        endpoint_url="https://" + event["requestContext"]["domainName"] + "/" + event["requestContext"]["stage"]
    )

    # Get all connection IDs
    response = dynamodb.scan(TableName=os.environ['WEBSOCKET_TABLE'])
    connectionIds = response.get('Items', [])

    # Handle "register" action
    if action_type == "register":
        username = body.get('username', '').strip()
        if not username:
            apigatewaymanagementapi.post_to_connection(
                Data="Registration failed: Username cannot be empty.",
                ConnectionId=connection_id
            )
            return {}
        
        # Save connection and username to DynamoDB
        dynamodb.put_item(
            TableName=os.environ['WEBSOCKET_TABLE'],
            Item={
                'connectionId': {'S': connection_id},
                'username': {'S': username}
            }
        )
        # Notify all users
        broadcast_message(f"{username} has joined the chat.", apigatewaymanagementapi, connectionIds)
        return {}

    # Handle "sendMessage" action
    if action_type == "sendMessage":
        # Save group message to chat history
        save_chat_message("group", message)
        broadcast_message(message, apigatewaymanagementapi, connectionIds)
        return {}

    # Handle "directMessage" action
    if action_type == "directMessage":
        to_username = body.get('to', '').strip()
        dm_message = body.get('message', '').strip()
        if not to_username or not dm_message:
            apigatewaymanagementapi.post_to_connection(
                Data="DM failed: Invalid payload.",
                ConnectionId=connection_id
            )
            return {}

        # Lookup recipient's connectionId
        response = dynamodb.scan(
            TableName=os.environ['WEBSOCKET_TABLE'],
            FilterExpression="username = :username",
            ExpressionAttributeValues={":username": {"S": to_username}}
        )
        if not response.get('Items'):
            # User does not exist in the table
            apigatewaymanagementapi.post_to_connection(
                Data=f"DM failed: User {to_username} does not exist or is not registered.",
                ConnectionId=connection_id
            )
            return {}

        recipient_connection_id = response['Items'][0]['connectionId']['S']
        if not recipient_connection_id:
            # User exists but is not online (connectionId missing)
            apigatewaymanagementapi.post_to_connection(
                Data=f"DM failed: User {to_username} is currently not online.",
                ConnectionId=connection_id
            )
            return {}

        # Send DM to the recipient
        apigatewaymanagementapi.post_to_connection(
            Data=dm_message,
            ConnectionId=recipient_connection_id
        )

        # Save direct message to chat history
        save_chat_message(f"{connection_id}-{to_username}", dm_message)

        # Acknowledge the sender
        apigatewaymanagementapi.post_to_connection(
            Data=f"Message sent to {to_username}: {dm_message}",
            ConnectionId=connection_id
        )

        return {}

    
    if action_type == "bot":
        bot_message = body.get('message', '').strip()
        if not bot_message:
            apigatewaymanagementapi.post_to_connection(
                Data="Bot request failed: Message cannot be empty.",
                ConnectionId=connection_id
            )
            return {}

        try:
            lex_response = boto3.client('lexv2-runtime').recognize_text(
                botId= os.environ['botId'],
                botAliasId= os.environ['botAliasId']',
                localeId='en_IN',
                sessionId='user123',  # Unique session ID
                text=bot_message
            )

            # Extract response messages from Lex
            lex_messages = lex_response.get('messages', [])
            bot_reply = " ".join(msg['content'] for msg in lex_messages) if lex_messages else "I couldn't process that request."

            # Save bot response to chat history
            save_chat_message("bot", bot_reply)

            # Broadcast bot response
            broadcast_message(f"Bot: {bot_reply}", apigatewaymanagementapi, connectionIds)
            return {}
        except Exception as e:
            apigatewaymanagementapi.post_to_connection(
                Data=f"Bot error: {str(e)}",
                ConnectionId=connection_id
            )
        return {}


    # Default: handle broadcast as group message
    broadcast_message(message, apigatewaymanagementapi, connectionIds)
    return {}

def broadcast_message(message, apigatewaymanagementapi, connectionIds):
    for connectionId in connectionIds:
        try:
            apigatewaymanagementapi.post_to_connection(
                Data=message,
                ConnectionId=connectionId['connectionId']['S']
            )
        except Exception as e:
            print(f"Error sending message to {connectionId['connectionId']['S']}: {str(e)}")

def save_chat_message(chat_id, message):
    """Save chat messages to the DynamoDB chat history table."""
    dynamodb.put_item(
        TableName=os.environ['CHAT_HISTORY_TABLE'],
        Item={
            'chatId': {'S': chat_id},
            'timestamp': {'S': datetime.datetime.utcnow().isoformat()},
            'message': {'S': message}
        }
    )
