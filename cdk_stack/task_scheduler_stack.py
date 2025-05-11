from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_dynamodb as dynamodb,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam
)
from constructs import Construct

class TaskSchedulerStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        lambda_layer = _lambda.LayerVersion(
            self,
            "TaskSchedulerLayer",
            code=_lambda.Code.from_asset("./lambda_layer/lambda_layer.zip"),
            compatible_runtimes=[_lambda.Runtime.PYTHON_3_9],
            description="Common libraries for task scheduler",
            layer_version_name="task-scheduler-dependencies",
        )

        # Create DynamoDB table for storing tasks
        task_table = dynamodb.Table(
            self, "TaskTable",
            partition_key=dynamodb.Attribute(
                name="task_id",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="run_at",
                type=dynamodb.AttributeType.STRING
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=RemovalPolicy.DESTROY,  # For development only, use RETAIN for production
            point_in_time_recovery=True
        )
        
        # Add GSI for querying by status
        task_table.add_global_secondary_index(
            index_name="status-index",
            partition_key=dynamodb.Attribute(
                name="status",
                type=dynamodb.AttributeType.STRING
            ),
            sort_key=dynamodb.Attribute(
                name="run_at",
                type=dynamodb.AttributeType.STRING
            )
        )

        # Create Lambda function for API endpoints
        api_lambda = _lambda.Function(
            self, "ApiFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="api_handler.handler",
            code=_lambda.Code.from_asset("lambda_functions/api"),
            timeout=Duration.seconds(30),
            environment={
                "TASK_TABLE_NAME": task_table.table_name
            },
            layers=[lambda_layer]
        )
        
        # Grant permissions to the API Lambda to access DynamoDB
        task_table.grant_read_write_data(api_lambda)
        
        # Create API Gateway
        api = apigw.RestApi(
            self, "TaskSchedulerApi",
            rest_api_name="Task Scheduler API",
            description="API for scheduling tasks"
        )
        
        # Add API resources and methods
        tasks_resource = api.root.add_resource("tasks")
        tasks_resource.add_method("POST", apigw.LambdaIntegration(api_lambda))
        tasks_resource.add_method("GET", apigw.LambdaIntegration(api_lambda))
        
        task_resource = tasks_resource.add_resource("{task_id}")
        task_resource.add_method("GET", apigw.LambdaIntegration(api_lambda))
        task_resource.add_method("DELETE", apigw.LambdaIntegration(api_lambda))
        
        # Create Lambda function for task execution
        executor_lambda = _lambda.Function(
            self, "ExecutorFunction",
            runtime=_lambda.Runtime.PYTHON_3_9,
            handler="executor_handler.handler",
            code=_lambda.Code.from_asset("lambda_functions/executor"),
            timeout=Duration.seconds(60),
            environment={
                "TASK_TABLE_NAME": task_table.table_name
            },
            layers=[lambda_layer]
        )
        
        # Grant permissions to the Executor Lambda
        task_table.grant_read_write_data(executor_lambda)
        
        # Create EventBridge rule to trigger task execution
        # This rule runs every minute to check for tasks that need to be executed
        rule = events.Rule(
            self, "ScheduleRule",
            schedule=events.Schedule.rate(Duration.minutes(1))
        )
        
        rule.add_target(targets.LambdaFunction(executor_lambda))
        
        # Add IAM policy to allow Lambda to make HTTP requests
        executor_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["*"],
                resources=["*"],
                effect=iam.Effect.ALLOW
            )
        )