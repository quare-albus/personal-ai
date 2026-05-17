import os
import json
from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Application
from telegram.request import HTTPXRequest
import google.generativeai as genai
from database import engine
from models import Base
from database import SessionLocal
from models import Task
from contextlib import asynccontextmanager
from thinking import extract_task, generate_today_plan
from config import TELEGRAM_BOT_TOKEN as BOT_TOKEN,  WEBHOOK_BASE_URL

Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):

    webhook_url = (
        f"{WEBHOOK_BASE_URL}/webhook"
    )

    print(
        "SETTING WEBHOOK:",
        webhook_url
    )

    await bot.set_webhook(
        url=webhook_url,

        drop_pending_updates=True
    )

    yield


request = HTTPXRequest(
    connect_timeout=20,
    read_timeout=20
)

app = FastAPI(
    lifespan=lifespan
)

bot = Bot(
    token=BOT_TOKEN,
    request=request
)

MEMORY_FILE = "user_memory.json"

def load_memory():
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)

def save_memory(data):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


@app.get("/test")
async def test():
    return {"working": True}


@app.get("/")
async def root():
    return {"status": "Planner AI running"}


@app.post("/webhook")
async def telegram_webhook(request: Request):

    db = SessionLocal()

    data = await request.json()

    print("Received data:", data)

    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    memory = load_memory()

    if str(chat_id) not in memory:
        memory[str(chat_id)] = {
            "tasks": []
        }

    if "add task" in text.lower():
        memory[str(chat_id)]["tasks"].append(text)

    if text == "/tasks":

        tasks = db.query(Task).all()

        response_text = ""

        for task in tasks:

            response_text += (
                f"{task.id}. "
                f"{task.task}\n"
            )

        await bot.send_message(
            chat_id=chat_id,
            text=response_text
        )

        return {"ok": True}
    
    if text == "/done":

        try:
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
        except Exception as e:
            print(e)

            await bot.send_message(
                chat_id=chat_id,
                text="Invalid command. Use /done <task_id>."
            )

        return {"ok": True}

    if text == "/today":

        tasks = db.query(Task).filter(
            Task.status == "pending"
        ).all()

        if not tasks:

            await bot.send_message(
                chat_id=chat_id,
                text="No pending tasks."
            )

            return {"ok": True}

        plan = generate_today_plan(tasks)

        await bot.send_message(
            chat_id=chat_id,
            text=plan
        )

        return {"ok": True}
    
    try:
        data = extract_task(text)

        print("Model response:", data.get("task"))

    except Exception as e:

        print(e)

        await bot.send_message(
            chat_id=chat_id,
            text="See logs for details. Could not extract task from message."
        )
        
        return {"ok": True}

    save_memory(memory)

    new_task = Task(

        chat_id=str(chat_id),

        task=data["task"],

        priority=data.get("priority", "medium"),

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

    return {"ok": True}
