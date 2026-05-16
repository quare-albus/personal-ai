import os
import json
from fastapi import FastAPI, Request
from telegram import Update, Bot
from telegram.ext import Application
from dotenv import load_dotenv
import google.generativeai as genai

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
    You are an intelligent planning assistant.

    User message:
    {text}

    Existing tasks:
    {memory[str(chat_id)]["tasks"]}

    If user mentions a task, summarize it clearly.
    """

    response = model.generate_content(prompt)

    ai_reply = response.text

    if "add task" in text.lower():
        memory[str(chat_id)]["tasks"].append(text)

    save_memory(memory)

    await bot.send_message(
        chat_id=chat_id,
        text=ai_reply
    )

    return {"ok": True}
