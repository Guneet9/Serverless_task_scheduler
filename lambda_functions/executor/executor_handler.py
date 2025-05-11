import json
import os
import boto3
import logging
import requests
from datetime import datetime, timedelta
from botocore.exceptions import ClientError

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb = boto3.resource('dynamodb')
table_name = os.environ['TASK_TABLE_NAME']
table = dynamodb.Table(table_name)

def handler(event, context):
    """
    Main handler for the task executor Lambda function.
    Triggered by EventBridge rule every minute.
    Finds tasks that need to be executed and processes them.
    """
    logger.info("Starting task execution check")
    
    try:
        # Get current time in ISO8601 format
        current_time = (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info(f"Current time: {current_time}")
        
        # Query tasks that are scheduled and due for execution
        response = table.query(
            IndexName='status-index',
            KeyConditionExpression='#status = :status AND #run_at <= :current_time',
            ExpressionAttributeNames={
                '#status': 'status',
                '#run_at': 'run_at'
            },
            ExpressionAttributeValues={
                ':status': 'scheduled',
                ':current_time': current_time
            }
        )
        
        tasks = response.get('Items', [])
        logger.info(f"Found {len(tasks)} tasks to execute")
        
        for task in tasks:
            execute_task(task)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Processed {len(tasks)} tasks',
                'timestamp': current_time
            })
        }
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def execute_task(task):
    """
    Execute a specific task based on its action type.
    Updates the task status in DynamoDB.
    """
    task_id = task['task_id']
    run_at = task['run_at']
    action = task['action']
    payload = task['payload']
    
    logger.info(f"Executing task {task_id} with action {action}")
    
    try:
        # Update task status to running
        update_task_status(task_id, run_at, 'running')
        
        # Execute the task based on action type
        if action == 'webhook':
            execute_webhook(payload)
        elif action == 'message':
            execute_message(payload)
        else:
            logger.warning(f"Unsupported action type: {action}")
            update_task_status(task_id, run_at, 'failed', f"Unsupported action type: {action}")
            return
        
        # Update task status to completed
        update_task_status(task_id, run_at, 'completed')
        
        # Handle recurrence if specified
        if 'recurrence' in task:
            schedule_next_occurrence(task)
    
    except Exception as e:
        logger.error(f"Task execution failed: {str(e)}")
        update_task_status(task_id, run_at, 'failed', str(e))

def execute_webhook(payload):
    """
    Execute a webhook task by making an HTTP request.
    """
    url = payload.get('url')
    data = payload.get('data', {})
    method = payload.get('method', 'POST')
    headers = payload.get('headers', {'Content-Type': 'application/json'})
    
    if not url:
        raise ValueError("Webhook URL is required")
    
    logger.info(f"Making {method} request to {url}")
    
    if method.upper() == 'GET':
        response = requests.get(url, params=data, headers=headers, timeout=30)
    else:
        response = requests.post(url, json=data, headers=headers, timeout=30)
    
    response.raise_for_status()
    logger.info(f"Webhook response: {response.status_code}| {response.text}")
    
    return response.status_code

def execute_message(payload):
    """
    Execute a message task (placeholder for demonstration).
    In a real implementation, this could send an email, SMS, etc.
    """
    message = payload.get('message', '')
    recipient = payload.get('recipient', '')
    
    logger.info(f"Sending message to {recipient}: {message}")
    
    # Placeholder for actual message sending logic
    # In a real implementation, you might use AWS SES, SNS, etc.
    
    return True

def update_task_status(task_id, run_at, status, error_message=None):
    """
    Update the status of a task in DynamoDB.
    """
    update_expression = "SET #status = :status, updated_at = :updated_at"
    expression_attribute_names = {'#status': 'status'}
    expression_attribute_values = {
        ':status': status,
        ':updated_at': datetime.utcnow().isoformat() + 'Z'
    }
    
    if error_message:
        update_expression += ", error_message = :error_message"
        expression_attribute_values[':error_message'] = error_message
    
    table.update_item(
        Key={
            'task_id': task_id,
            'run_at': run_at
        },
        UpdateExpression=update_expression,
        ExpressionAttributeNames=expression_attribute_names,
        ExpressionAttributeValues=expression_attribute_values
    )
    
    logger.info(f"Updated task {task_id} status to {status}")

def schedule_next_occurrence(task):
    """
    Schedule the next occurrence of a recurring task.
    """
    recurrence = task['recurrence']
    task_id = task['task_id']
    run_at = task['run_at']
    
    # Calculate the next run time based on recurrence pattern
    current_time = datetime.fromisoformat(run_at.replace('Z', '+00:00'))
    
    if recurrence == 'daily':
        next_run = current_time.replace(day=current_time.day + 1)
    elif recurrence == 'weekly':
        next_run = current_time.replace(day=current_time.day + 7)
    elif recurrence == 'monthly':
        # Simple implementation - might not handle month boundaries correctly
        if current_time.month == 12:
            next_run = current_time.replace(year=current_time.year + 1, month=1)
        else:
            next_run = current_time.replace(month=current_time.month + 1)
    else:
        logger.warning(f"Unsupported recurrence pattern: {recurrence}")
        return
    
    next_run_at = next_run.isoformat().replace('+00:00', 'Z')
    
    # Create a new task for the next occurrence
    new_task_id = f"{task_id}-{next_run_at}"
    new_task = {
        'task_id': new_task_id,
        'action': task['action'],
        'payload': task['payload'],
        'run_at': next_run_at,
        'status': 'scheduled',
        'recurrence': recurrence,
        'created_at': datetime.utcnow().isoformat() + 'Z',
        'updated_at': datetime.utcnow().isoformat() + 'Z',
        'parent_task_id': task_id
    }
    
    table.put_item(Item=new_task)
    logger.info(f"Scheduled next occurrence of task {task_id} as {new_task_id} at {next_run_at}")