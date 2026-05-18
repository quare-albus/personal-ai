import os
import json

from openai import OpenAI

from context_builder import build_context


client = OpenAI(

    api_key=os.getenv(
        "OPENROUTER_API_KEY"
    ),

    base_url="https://openrouter.ai/api/v1"
)

MODEL_NAME = "openrouter/free"


def extract_task(text):

    prompt = f"""
    Extract task information.

    Message:
    {text}

    Return ONLY valid JSON.

    Example:
    {{
        "task": "Finish report",
        "priority": "high"
    }}

    Priority must be:
    low, medium, or high.

    If message is not a task:

    {{
        "not_task": true
    }}
    """

    response = client.chat.completions.create(

        model=MODEL_NAME,

        messages=[
            {
                "role": "system",
                "content": (
                    "You are a task "
                    "extraction system."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    print("MODEL RESPONSE:")
    print(content)

    clean_text = (
        content
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    task_json = json.loads(clean_text)

    if task_json.get("not_task"):

        raise ValueError("Message is not a task.")
    
    return task_json


def extract_goal(text):

    prompt = f"""
    Extract the user's goal from the message.

    Message:
    {text}

    Return ONLY valid JSON.

    Example:
    {{
        "title": "Launch the team newsletter",
        "description": "Create and ship a weekly email newsletter to update stakeholders.",
        "why": "Keep the team aligned and share progress with leadership.",
        "category": "communication",
        "priority": "medium"
    }}

    If the message does not describe a goal, return:
    {{"not_goal": true}}
    """

    response = client.chat.completions.create(

        model=MODEL_NAME,

        messages=[
            {
                "role": "system",
                "content": (
                    "You are a goal planning assistant."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    print("GOAL MODEL RESPONSE:")
    print(content)

    clean_text = (
        content
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    goal_json = json.loads(clean_text)
    return goal_json


def generate_tasks_for_goal(goal):

    prompt = f"""
    Generate a set of practical tasks that help achieve this goal.

    Goal title: {goal.title}
    Description: {goal.description or ''}
    Why: {goal.why or ''}
    Category: {goal.category or ''}
    Priority: {goal.priority or 'medium'}

    Return ONLY valid JSON array of objects with keys: task, priority.
    Example:
    [
      {{"task": "Draft the first newsletter", "priority": "high"}},
      {{"task": "Collect input from the product team", "priority": "medium"}}
    ]
    """

    response = client.chat.completions.create(

        model=MODEL_NAME,

        messages=[
            {
                "role": "system",
                "content": (
                    "You are a task generation assistant that converts goals into action items."
                )
            },
            {
                "role": "user",
                "content":
                    f"Execution Context:\n{json.dumps(
                        build_context(),
                        indent=2
                    )}"
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    clean_text = (
        content
        .replace("```json", "")
        .replace("```", "")
        .strip()
    )

    tasks = json.loads(clean_text)
    if isinstance(tasks, dict):
        tasks = [tasks]
    return tasks


def generate_today_plan(tasks):

    task_text = ""

    for task in tasks:

        task_text += (
            f"- {task.task} "
            f"({task.priority})\n"
        )

    prompt = f"""
    Create a realistic plan for today.

    Tasks:
    {task_text}

    Rules:
    - prioritize high priority tasks
    - avoid overload
    - include breaks
    - realistic workload
    - concise format

    Return readable text only.
    """

    response = client.chat.completions.create(

        model=MODEL_NAME,

        messages=[
            {
                "role": "system",
                "content": (
                    "You are an adaptive "
                    "productivity planner."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    return content