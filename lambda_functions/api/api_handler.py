import json
import os
import uuid
import boto3
import logging
import decimal
from datetime import datetime
from botocore.exceptions import ClientError

# Helper class to convert a DynamoDB item to JSON
class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            if o % 1 > 0:
                return float(o)
            else:
                return int(o)
        return super(DecimalEncoder, self).default(o)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table_name = os.environ['TASK_TABLE_NAME']
table = dynamodb.Table(table_name)

def handler(event, context):
    """
    Main handler for the API Lambda function.
    Routes requests based on HTTP method and path.
    """
    logger.info(f"Event: {json.dumps(event)}")
    
    http_method = event['httpMethod']
    resource_path = event['resource']
    
    # Route the request based on method and path
    if http_method == 'POST' and resource_path == '/tasks':
        return schedule_task(event)
    elif http_method == 'GET' and resource_path == '/tasks':
        return list_tasks(event)
    elif http_method == 'GET' and resource_path == '/tasks/{task_id}':
        return get_task(event)
    elif http_method == 'DELETE' and resource_path == '/tasks/{task_id}':
        return delete_task(event)
    else:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Unsupported route'})
        }

def schedule_task(event):
    """
    Schedule a new task.
    """
    try:
        # Parse request body
        body = json.loads(event['body'])
        
        # Validate required fields
        required_fields = ['action', 'payload', 'run_at']
        for field in required_fields:
            if field not in body:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': f'Missing required field: {field}'})
                }
        
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Parse and validate the run_at timestamp
        try:
            run_at = body['run_at']
            # Validate ISO8601 format by parsing it
            datetime.fromisoformat(run_at.replace('Z', '+00:00'))
        except ValueError:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Invalid run_at format. Use ISO8601 format (YYYY-MM-DDTHH:MM:SSZ)'})
            }
        
        # Create task item
        current_time = datetime.utcnow().isoformat() + 'Z'
        task_item = {
            'task_id': task_id,
            'action': body['action'],
            'payload': body['payload'],
            'run_at': run_at,
            'status': 'scheduled',
            'created_at': current_time,
            'updated_at': current_time
        }
        
        # Add recurrence if provided (optional)
        if 'recurrence' in body:
            task_item['recurrence'] = body['recurrence']
        
        # Save to DynamoDB
        table.put_item(Item=task_item)
        
        return {
            'statusCode': 201,
            'body': json.dumps({
                'message': 'Task scheduled successfully',
                'task_id': task_id
            })
        }
    
    except ClientError as e:
        logger.error(f"DynamoDB error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to schedule task'})
        }
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def list_tasks(event):
    """
    List all tasks or filter by status.
    """
    try:
        # Check for query parameters
        query_params = event.get('queryStringParameters', {}) or {}
        status_filter = query_params.get('status')
        
        if status_filter:
            # Query by status using GSI
            response = table.query(
                IndexName='status-index',
                KeyConditionExpression='#status = :status',
                ExpressionAttributeNames={
                    '#status': 'status'
                },
                ExpressionAttributeValues={
                    ':status': status_filter
                }
            )
        else:
            # Scan all tasks
            response = table.scan()
        
        tasks = response.get('Items', [])
        
        return {
            'statusCode': 200,
            'body': json.dumps({'tasks': tasks}, cls=DecimalEncoder)
        }
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def get_task(event):
    """
    Get a specific task by ID.
    """
    try:
        # Get task ID from path parameters
        task_id = event['pathParameters']['task_id']
        
        # Query DynamoDB for the task
        response = table.query(
            KeyConditionExpression='task_id = :task_id',
            ExpressionAttributeValues={
                ':task_id': task_id
            }
        )
        
        tasks = response.get('Items', [])
        
        if not tasks:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Task not found'})
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps({'task': tasks[0]}, cls=DecimalEncoder)
        }
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def delete_task(event):
    """
    Delete a task by ID.
    """
    try:
        # Get task ID from path parameters
        task_id = event['pathParameters']['task_id']
        
        # Query DynamoDB for the task to get the run_at value (needed for the composite key)
        response = table.query(
            KeyConditionExpression='task_id = :task_id',
            ExpressionAttributeValues={
                ':task_id': task_id
            }
        )
        
        tasks = response.get('Items', [])
        
        if not tasks:
            return {
                'statusCode': 404,
                'body': json.dumps({'error': 'Task not found'})
            }
        
        # Delete the task
        run_at = tasks[0]['run_at']
        table.delete_item(
            Key={
                'task_id': task_id,
                'run_at': run_at
            }
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Task deleted successfully'})
        }
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }