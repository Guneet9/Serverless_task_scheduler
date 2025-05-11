# Serverless Task Scheduler - Design Document

## Overview

The Serverless Task Scheduler is a cloud-native application that allows users to schedule tasks to run at specific times in the future. It leverages AWS serverless services to provide a scalable, cost-effective solution without the need to manage any infrastructure.

## Architecture

The application follows a serverless event-driven architecture with the following components:

1. **API Gateway**: Provides HTTP endpoints for task management
2. **API Lambda Function**: Processes API requests and interacts with DynamoDB
3. **DynamoDB**: Stores task information and status
4. **EventBridge Rule**: Triggers the executor Lambda function on a schedule
5. **Executor Lambda Function**: Processes due tasks and updates their status

## AWS Services Used

| Service | Purpose |
|---------|---------|
| AWS Lambda | Serverless compute for API handling and task execution |
| Amazon API Gateway | RESTful API endpoints for task management |
| Amazon DynamoDB | NoSQL database for task storage |
| Amazon EventBridge | Scheduled trigger for the executor Lambda |
| AWS IAM | Security and access control |
| AWS CDK | Infrastructure as Code for deployment |

## Data Model

### DynamoDB Schema

**Table Name**: TaskTable

**Primary Key**:
- Partition Key: `task_id` (String)
- Sort Key: `run_at` (String, ISO8601 timestamp)

**Global Secondary Index**:
- Name: `status-index`
- Partition Key: `status` (String)
- Sort Key: `run_at` (String)

**Attributes**:
- `task_id`: Unique identifier for the task (UUID)
- `run_at`: When the task should be executed (ISO8601 timestamp)
- `action`: Type of action to perform (e.g., webhook, message)
- `payload`: Data required for the action (JSON object)
- `status`: Current status of the task (scheduled, running, completed, failed)
- `created_at`: When the task was created (ISO8601 timestamp)
- `updated_at`: When the task was last updated (ISO8601 timestamp)
- `recurrence`: Optional recurrence pattern (daily, weekly, monthly)
- `error_message`: Optional error message if the task failed
- `parent_task_id`: Optional reference to the parent task for recurring tasks

## API Design

### Endpoints

1. **POST /tasks**
   - Schedule a new task
   - Request body includes action, payload, run_at, and optional recurrence
   - Returns task_id

2. **GET /tasks**
   - List all tasks or filter by status
   - Optional query parameter: status
   - Returns array of tasks

3. **GET /tasks/{task_id}**
   - Get details of a specific task
   - Returns task object

4. **DELETE /tasks/{task_id}**
   - Delete a specific task
   - Returns success message

## Task Execution Flow

1. User schedules a task via the API
2. API Lambda stores the task in DynamoDB with "scheduled" status
3. EventBridge rule triggers the Executor Lambda every minute
4. Executor Lambda queries DynamoDB for tasks that are due
5. For each due task:
   - Update status to "running"
   - Execute the task based on its action type
   - Update status to "completed" or "failed"
   - If recurring, schedule the next occurrence

## Supported Actions

1. **webhook**: Makes an HTTP request to a specified URL with a JSON payload
2. **message**: Simulated message sending (placeholder for demonstration)

## Trade-offs and Considerations

### Pros

1. **Serverless Architecture**:
   - No infrastructure to manage
   - Pay-per-use pricing model
   - Automatic scaling

2. **Event-Driven Design**:
   - Decoupled components
   - Easy to extend with new action types
   - Resilient to failures

3. **DynamoDB**:
   - Highly available and durable
   - Scales automatically
   - Fast access patterns with GSI

### Cons

1. **Scheduling Precision**:
   - Minimum interval of 1 minute
   - Potential slight delays due to Lambda cold starts

2. **Cost Considerations**:
   - EventBridge rule runs every minute, which could lead to higher costs for long periods with no tasks
   - DynamoDB read/write capacity needs to be monitored

3. **Limitations**:
   - No built-in retry mechanism for failed tasks
   - Limited to AWS ecosystem

## Security Considerations

1. **IAM Roles**: Each Lambda function has a specific IAM role with least privilege permissions
2. **API Authentication**: Not implemented in this version, but could be added using API Gateway authorizers
3. **Data Validation**: Input validation on all API requests

## Monitoring and Logging

1. **CloudWatch Logs**: All Lambda functions log to CloudWatch
2. **Error Handling**: Comprehensive error handling with detailed error messages

## Future Enhancements

1. **Authentication and Authorization**: Add API Gateway authorizers
2. **Retry Mechanism**: Implement automatic retries for failed tasks
3. **Additional Action Types**: Support for SQS, SNS, Lambda invocations
4. **Web UI**: Create a simple dashboard for task management
5. **Advanced Recurrence**: Support for more complex recurrence patterns
6. **Dead Letter Queue**: Add DLQ for failed tasks
7. **Metrics and Alarms**: Add CloudWatch alarms for monitoring

## Conclusion

The Serverless Task Scheduler provides a flexible, scalable solution for scheduling future tasks without managing infrastructure. It leverages AWS serverless services to provide a cost-effective, reliable system that can be easily extended to support additional features and action types.