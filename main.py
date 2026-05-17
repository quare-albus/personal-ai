import os
import json
from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Application
from dotenv import load_dotenv
import google.generativeai as genai
from database import engine
from models import Base
from database import SessionLocal
from models import Task

Base.metadata.create_all(bind=engine)

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_API_KEY)

model = genai.GenerativeModel("gemini-2.5-flash")

app = FastAPI()

bot = Bot(token=BOT_TOKEN)

MEMORY_FILE = "user_memory.json"


def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


@app.get("/")
async def root():
    return {"status": "Planner AI running"}


@app.post("/webhook")
async def telegram_webhook(request: Request):

    data = await request.json()

    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    memory = load_memory()

    if str(chat_id) not in memory:
        memory[str(chat_id)] = {
            "tasks": []
        }

    prompt = f"""
        Extract task information from the message.

        Message:
        {text}

        Return ONLY valid JSON.

        Example:
        {{
        "task": "Finish report",
        "priority": "high"
        }}
        """

    response = model.generate_content(prompt)

    data = json.loads(response.text)

    if "add task" in text.lower():
        memory[str(chat_id)]["tasks"].append(text)

    if text == "/tasks":

        tasks = db.query(Task).filter(
            Task.chat_id == str(chat_id)
        ).all()

        reply = ""

        for task in tasks:

            reply += (
                f"{task.id}. "
                f"{task.task} "
                f"[{task.status}]\n"
            )

        await bot.send_message(
            chat_id=chat_id,
            text=reply or "No tasks."
        )

        return {"ok": True}
    
    if text.startswith("/done"):

        task_id = int(text.split(" ")[1])

        task = db.query(Task).filter(
            Task.id == task_id
        ).first()

        if task:

            task.status = "completed"

            db.commit()

            await bot.send_message(
                chat_id=chat_id,
                text="Task completed."
            )

        return {"ok": True}


    save_memory(memory)

    db = SessionLocal()

    new_task = Task(

        chat_id=str(chat_id),

        task=data["task"],

        priority=data["priority"],

        status="pending"
    )

    db.add(new_task)

    db.commit()

    await bot.send_message(
        chat_id=chat_id,
        text=(
            f"Task added:\n"
            f"{data['task']}\n"
            f"Priority: {data['priority']}"
        )
    )

    if text.startswith("/today"):
        tasks = db.query(Task).filter(
                Task.chat_id == str(chat_id),
                Task.status == "pending"
            ).all()

        task_list = [
            task.task for task in tasks
        ]

        prompt = f"""
        Generate a realistic plan for today.

        Tasks:
        {task_list}

        Constraints:
        - avoid burnout
        - prioritize important tasks
        - include breaks
        """

        response = model.generate_content(prompt)

        await bot.send_message(
            chat_id=chat_id,
            text=response.text
        )

    return {"ok": True}
