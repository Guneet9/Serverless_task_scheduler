# Serverless Task Scheduler

A serverless application for scheduling tasks to run at specific times in the future, built using AWS CDK and Python.

## Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │
│   API Gateway   │────>│   API Lambda    │────>│    DynamoDB     │
│                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                         │
                                                         │
┌─────────────────┐     ┌─────────────────┐              │
│                 │     │                 │              │
│  EventBridge    │────>│ Executor Lambda │──────────────┘
│    (1 min)      │     │                 │
└─────────────────┘     └─────────────────┘


  Client                    AWS Cloud                      External
    │                                                        │
    │                                                        │
    │    ┌─────────────────────────────────────────┐         │
    │    │                                         │         │
    ├───>│ 1. Schedule Task (POST /tasks)          │         │
    │    │                                         │         │
    │<───┤ 2. Return task_id                       │         │
    │    │                                         │         │
    │    │ 3. EventBridge triggers every minute    │         │
    │    │                                         │         │
    │    │ 4. Executor finds & processes tasks     │         │
    │    │                                         │         │
    │    │ 5. Execute task action                  │────────>│
    │    │    (webhook, message, etc.)             │         │
    │    │                                         │         │
    │    │ 6. Update task status                   │         │
    │    │                                         │         │
    │    └─────────────────────────────────────────┘         │
```

### Components

1. **API Gateway**: Provides HTTP endpoints for scheduling and managing tasks.
2. **API Lambda Function**: Handles API requests for creating, retrieving, and deleting tasks.
3. **DynamoDB**: Stores task information including scheduling details and status.
4. **EventBridge Rule**: Triggers the executor Lambda function every minute.
5. **Executor Lambda Function**: Checks for tasks that need to be executed and processes them.

### Task Flow

1. User schedules a task via the API with an action, payload, and execution time.
2. The API Lambda stores the task in DynamoDB with a "scheduled" status.
3. The EventBridge rule triggers the Executor Lambda every minute.
4. The Executor Lambda queries DynamoDB for tasks that are due for execution.
5. For each task, the Executor Lambda:
   - Updates the task status to "running"
   - Executes the task based on its action type
   - Updates the task status to "completed" or "failed"
   - If the task is recurring, schedules the next occurrence

## Supported Actions

1. **Webhook**: Makes an HTTP request to a specified URL with a JSON payload.
2. **Message**: Simulated message sending (placeholder for demonstration).

## Features

- Schedule tasks to run at specific times
- Support for recurring tasks (daily, weekly, monthly)
- Task status tracking (scheduled, running, completed, failed)
- API for task management (create, list, get, delete)

## Prerequisites

- AWS Account
- AWS CLI configured
- Node.js and npm installed
- Python 3.9+ installed
- AWS CDK installed (`npm install -g aws-cdk`)

## Deployment

1. Clone the repository:
   ```
   git clone <repository-url>
   cd serverless-task-scheduler
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Bootstrap the CDK (if you haven't already):
   ```
   cdk bootstrap
   ```

5. Deploy the stack:
   ```
   cdk deploy
   ```

6. Note the API Gateway URL from the output.

## Local Testing

### Unit Tests

Run the unit tests:
```
python -m pytest tests/
```

### Local API Testing

You can test the API locally using the AWS SAM CLI:

1. Install AWS SAM CLI:
   ```
   pip install aws-sam-cli
   ```

2. Generate SAM template:
   ```
   cdk synth --no-staging > template.yaml
   ```

3. Start local API:
   ```
   sam local start-api
   ```

4. Test with curl:
   ```
   curl -X POST http://localhost:3000/tasks \
     -H "Content-Type: application/json" \
     -d '{
       "action": "webhook",
       "payload": {
         "url": "https://example.com/notify",
         "data": { "message": "Hello, this is your scheduled task!" }
       },
       "run_at": "2024-06-10T15:00:00Z"
     }'
   ```

## API Reference

### Schedule a Task

```
POST /tasks
```

Request body:
```json
{
  "action": "webhook",
  "payload": {
    "url": "https://example.com/notify",
    "data": { "message": "Hello, this is your scheduled task!" }
  },
  "run_at": "2024-06-10T15:00:00Z",
  "recurrence": "daily"  // Optional
}
```

Response:
```json
{
  "message": "Task scheduled successfully",
  "task_id": "123e4567-e89b-12d3-a456-426614174000"
}
```

### List Tasks

```
GET /tasks
```

Query parameters:
- `status`: Filter by status (optional)

Response:
```json
{
  "tasks": [
    {
      "task_id": "123e4567-e89b-12d3-a456-426614174000",
      "action": "webhook",
      "payload": { ... },
      "run_at": "2024-06-10T15:00:00Z",
      "status": "scheduled",
      "created_at": "2024-06-01T10:00:00Z",
      "updated_at": "2024-06-01T10:00:00Z"
    }
  ]
}
```

### Get Task

```
GET /tasks/{task_id}
```

Response:
```json
{
  "task": {
    "task_id": "123e4567-e89b-12d3-a456-426614174000",
    "action": "webhook",
    "payload": { ... },
    "run_at": "2024-06-10T15:00:00Z",
    "status": "scheduled",
    "created_at": "2024-06-01T10:00:00Z",
    "updated_at": "2024-06-01T10:00:00Z"
  }
}
```

### Delete Task

```
DELETE /tasks/{task_id}
```

Response:
```json
{
  "message": "Task deleted successfully"
}
```

## Design Considerations

### DynamoDB Schema

- **Partition Key**: `task_id` (UUID)
- **Sort Key**: `run_at` (ISO8601 timestamp)
- **GSI**: `status-index` with partition key `status` and sort key `run_at`

This schema allows for:
- Efficient retrieval of tasks by ID
- Querying tasks by status and execution time
- Sorting tasks by execution time

### Scalability

- DynamoDB automatically scales to handle increased load
- Lambda functions scale automatically based on the number of concurrent requests
- EventBridge rule ensures tasks are executed on time without manual intervention

### Limitations

- The minimum task execution interval is 1 minute (due to the EventBridge rule frequency)
- Tasks scheduled within the same minute might be executed in any order
- No built-in retry mechanism for failed tasks (could be added as an enhancement)

## Future Enhancements

1. Add authentication and authorization
2. Implement retry mechanism for failed tasks
3. Add more action types (e.g., SQS, SNS, Lambda)
4. Create a web UI for task management
5. Add CloudWatch alarms for monitoring
6. Implement dead-letter queue for failed tasks
7. Add support for more complex recurrence patterns

## License

[MIT License](LICENSE)