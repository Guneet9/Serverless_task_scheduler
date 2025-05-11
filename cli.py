#!/usr/bin/env python3
"""
Command Line Interface for the Serverless Task Scheduler.
This is a bonus feature that allows users to schedule tasks from the command line.
"""

import argparse
import json
import requests
import sys
from datetime import datetime, timedelta

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Serverless Task Scheduler CLI')
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Schedule task command
    schedule_parser = subparsers.add_parser('schedule', help='Schedule a new task')
    schedule_parser.add_argument('--action', required=True, choices=['webhook', 'message'], 
                                help='Action type (webhook or message)')
    schedule_parser.add_argument('--payload', required=True, type=str, 
                                help='JSON payload for the task')
    schedule_parser.add_argument('--run-at', required=False, type=str, 
                                help='When to run the task (ISO8601 format, e.g., 2024-06-10T15:00:00Z)')
    schedule_parser.add_argument('--delay', required=False, type=int, 
                                help='Delay in minutes from now')
    schedule_parser.add_argument('--recurrence', required=False, choices=['daily', 'weekly', 'monthly'], 
                                help='Recurrence pattern (optional)')
    
    # List tasks command
    list_parser = subparsers.add_parser('list', help='List all tasks')
    list_parser.add_argument('--status', required=False, 
                            choices=['scheduled', 'running', 'completed', 'failed'], 
                            help='Filter by status')
    
    # Get task command
    get_parser = subparsers.add_parser('get', help='Get a specific task')
    get_parser.add_argument('--task-id', required=True, type=str, help='Task ID')
    
    # Delete task command
    delete_parser = subparsers.add_parser('delete', help='Delete a specific task')
    delete_parser.add_argument('--task-id', required=True, type=str, help='Task ID')
    
    # API endpoint
    parser.add_argument('--api-url', required=True, type=str, 
                        help='API Gateway URL (e.g., https://abc123.execute-api.us-east-1.amazonaws.com/prod)')
    
    return parser.parse_args()

def schedule_task(args):
    """Schedule a new task."""
    try:
        # Parse payload
        payload = json.loads(args.payload)
        
        # Determine run_at time
        if args.run_at:
            run_at = args.run_at
        elif args.delay:
            # Calculate future time based on delay
            future_time = datetime.utcnow() + timedelta(minutes=args.delay)
            run_at = future_time.isoformat() + 'Z'
        else:
            print("Error: Either --run-at or --delay must be specified")
            sys.exit(1)
        
        # Create request body
        request_body = {
            'action': args.action,
            'payload': payload,
            'run_at': run_at
        }
        
        # Add recurrence if specified
        if args.recurrence:
            request_body['recurrence'] = args.recurrence
        
        # Make API request
        response = requests.post(
            f"{args.api_url}/tasks",
            json=request_body,
            headers={'Content-Type': 'application/json'}
        )
        
        # Check response
        if response.status_code == 201:
            result = response.json()
            print(f"Task scheduled successfully with ID: {result['task_id']}")
            print(f"Will run at: {run_at}")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    
    except json.JSONDecodeError:
        print("Error: Invalid JSON payload")
        sys.exit(1)
    except requests.RequestException as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

def list_tasks(args):
    """List all tasks or filter by status."""
    try:
        # Prepare URL with optional status filter
        url = f"{args.api_url}/tasks"
        if args.status:
            url += f"?status={args.status}"
        
        # Make API request
        response = requests.get(url)
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            tasks = result.get('tasks', [])
            
            if not tasks:
                print("No tasks found")
                return
            
            # Print tasks in a table format
            print(f"{'Task ID':<36} | {'Action':<10} | {'Status':<10} | {'Run At':<25}")
            print("-" * 85)
            
            for task in tasks:
                print(f"{task['task_id']:<36} | {task['action']:<10} | {task['status']:<10} | {task['run_at']:<25}")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    
    except requests.RequestException as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

def get_task(args):
    """Get a specific task by ID."""
    try:
        # Make API request
        response = requests.get(f"{args.api_url}/tasks/{args.task_id}")
        
        # Check response
        if response.status_code == 200:
            result = response.json()
            task = result.get('task', {})
            
            # Print task details
            print(f"Task ID: {task['task_id']}")
            print(f"Action: {task['action']}")
            print(f"Status: {task['status']}")
            print(f"Run At: {task['run_at']}")
            print(f"Created At: {task['created_at']}")
            print(f"Updated At: {task['updated_at']}")
            print("Payload:")
            print(json.dumps(task['payload'], indent=2))
            
            if 'recurrence' in task:
                print(f"Recurrence: {task['recurrence']}")
            
            if 'error_message' in task:
                print(f"Error Message: {task['error_message']}")
        elif response.status_code == 404:
            print("Task not found")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    
    except requests.RequestException as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

def delete_task(args):
    """Delete a specific task by ID."""
    try:
        # Make API request
        response = requests.delete(f"{args.api_url}/tasks/{args.task_id}")
        
        # Check response
        if response.status_code == 200:
            print("Task deleted successfully")
        elif response.status_code == 404:
            print("Task not found")
        else:
            print(f"Error: {response.status_code}")
            print(response.text)
    
    except requests.RequestException as e:
        print(f"Error: {str(e)}")
        sys.exit(1)

def main():
    """Main entry point for the CLI."""
    args = parse_args()
    
    if args.command == 'schedule':
        schedule_task(args)
    elif args.command == 'list':
        list_tasks(args)
    elif args.command == 'get':
        get_task(args)
    elif args.command == 'delete':
        delete_task(args)
    else:
        print("Error: No command specified")
        sys.exit(1)

if __name__ == '__main__':
    main()