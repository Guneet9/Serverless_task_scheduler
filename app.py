#!/usr/bin/env python3
import os
from aws_cdk import App

from cdk_stack.task_scheduler_stack import TaskSchedulerStack

app = App()
TaskSchedulerStack(app, "TaskSchedulerStack")

app.synth()