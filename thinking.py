import os
import json

from openai import OpenAI


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