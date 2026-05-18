import json
import os
import re
import context_builder
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from telegram import Bot
from telegram.request import HTTPXRequest

from config import TELEGRAM_BOT_TOKEN as BOT_TOKEN, WEBHOOK_BASE_URL
from database import SessionLocal, engine
from sqlalchemy import desc
from models import Base, Goal, Task
from thinking import (
    extract_goal,
    extract_task,
    generate_tasks_for_goal,
    generate_today_plan,
)

Base.metadata.create_all(bind=engine)

MEMORY_FILE = "user_memory.json"

request = HTTPXRequest(
    connect_timeout=20,
    read_timeout=20
)

bot = Bot(token=BOT_TOKEN, request=request)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if WEBHOOK_BASE_URL:
        webhook_url = f"{WEBHOOK_BASE_URL.rstrip('/')}/webhook"
        print("SETTING WEBHOOK:", webhook_url)
        await bot.set_webhook(url=webhook_url, drop_pending_updates=True)
    yield


app = FastAPI(lifespan=lifespan)


def load_memory() -> dict:
    if not os.path.exists(MEMORY_FILE):
        return {}
    with open(MEMORY_FILE, "r") as f:
        return json.load(f)


def save_memory(data: dict):
    with open(MEMORY_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_chat_memory(chat_id: int) -> tuple[dict, dict]:
    memory = load_memory()
    key = str(chat_id)
    if key not in memory:
        memory[key] = {"pending_goal": None}
    return memory, memory[key]


def normalize_priority(value: str) -> str:
    if not value:
        return "medium"
    normalized = value.strip().lower()
    if normalized in {"low", "medium", "high"}:
        return normalized
    if "urgent" in normalized or "high" in normalized:
        return "high"
    if "low" in normalized or "easy" in normalized:
        return "low"
    return "medium"


def goal_follow_up_prompt(field: str) -> str:
    if field == "why":
        return "Why is this goal important to you?"
    if field == "category":
        return "What category does this goal belong to? (for example: career, health, learning, finance)"
    if field == "priority":
        return "What priority would you assign to this goal? (low, medium, or high)"
    return "Please provide more detail about this goal."


def format_goal_summary(goal: Goal) -> str:
    return (
        f"Goal created: {goal.title}\n"
        f"Category: {goal.category or 'unspecified'}\n"
        f"Priority: {goal.priority}\n"
        f"Why: {goal.why or 'not provided'}"
    )


def parse_goal_id(text: str) -> Optional[int]:
    match = re.search(r"\b(\d+)\b", text)
    return int(match.group(1)) if match else None


def create_goal(db, chat_id: str, payload: dict) -> Goal:
    goal = Goal(
        chat_id=chat_id,
        title=payload.get("title") or payload.get("description") or "Untitled goal",
        description=payload.get("description"),
        why=payload.get("why"),
        category=payload.get("category"),
        priority=normalize_priority(payload.get("priority", "medium")),
        status=payload.get("status", "active"),
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def build_pending_goal(goal_data: dict) -> dict:
    required = [field for field in ["why", "category"] if not goal_data.get(field)]
    return {"goal": goal_data, "awaiting": required}


def fill_pending_goal(pending: dict, text: str) -> tuple[dict, Optional[str], Optional[dict]]:
    awaiting = pending.get("awaiting", [])
    if not awaiting:
        return pending, None, pending.get("goal")

    field = awaiting[0]
    if field == "priority":
        value = normalize_priority(text)
        if value not in {"low", "medium", "high"}:
            return pending, goal_follow_up_prompt(field), None
        pending["goal"][field] = value
    else:
        pending["goal"][field] = text.strip()

    pending["awaiting"] = awaiting[1:]
    if pending["awaiting"]:
        return pending, goal_follow_up_prompt(pending["awaiting"][0]), None
    return pending, None, pending["goal"]


def command_menu() -> str:
    return (
        "Welcome! Use these commands to manage goals and tasks:\n"
        "/start - show this menu\n"
        "/goal create <goal description> - create a new goal\n"
        "/goals - list your goals\n"
        "/goal complete <goal_id> - complete a goal\n"
        "/goal generate <goal_id> - auto-generate tasks for a goal\n"
        "/tasks - list your tasks\n"
        "/done <task_id> - mark a task done\n"
        "/today - create a plan for pending tasks\n"
        "/cancel - cancel goal setup"
    )


@app.get("/test")
async def test():
    return {"working": True}


@app.get("/")
async def root():
    return {"status": "Planner AI running"}


@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "" ).strip()
    if not chat_id or not text:
        return {"ok": False}

    memory, chat_memory = get_chat_memory(chat_id)
    pending = chat_memory.get("pending_goal")
    text_lower = text.lower()

    if text_lower in {"/start", "/start", "/help", "help"}:
        await bot.send_message(chat_id=chat_id, text=command_menu())
        return {"ok": True}

    if text_lower in {"/cancel", "cancel"} and pending:
        chat_memory["pending_goal"] = None
        save_memory(memory)
        await bot.send_message(chat_id=chat_id, text="Goal creation cancelled.")
        return {"ok": True}

    if pending and not text_lower.startswith("/"):
        pending, follow_up, complete_goal_data = fill_pending_goal(pending, text)
        if follow_up:
            chat_memory["pending_goal"] = pending
            save_memory(memory)
            await bot.send_message(chat_id=chat_id, text=follow_up)
            return {"ok": True}

        if complete_goal_data:
            with SessionLocal() as db:
                goal = create_goal(db, str(chat_id), complete_goal_data)
                chat_memory["pending_goal"] = None
                save_memory(memory)
                await bot.send_message(chat_id=chat_id, text=format_goal_summary(goal))
                return {"ok": True}

    command_goal_id = parse_goal_id(text_lower)
    if text_lower in {"/goals", "/goal list", "list goals"}:
        with SessionLocal() as db:
            goals = db.query(Goal).filter(Goal.chat_id == str(chat_id)).all()
        if not goals:
            await bot.send_message(chat_id=chat_id, text="You have no goals yet.")
            return {"ok": True}

        goal_lines = [f"{goal.id}. {goal.title} [{goal.priority}] ({goal.status})" for goal in goals]
        await bot.send_message(chat_id=chat_id, text="Your goals:\n" + "\n".join(goal_lines))
        return {"ok": True}

    if text_lower.startswith("/goal complete") or text_lower.startswith("/goal done"):
        if command_goal_id is None:
            await bot.send_message(chat_id=chat_id, text="Usage: /goal complete <goal_id>")
            return {"ok": True}

        with SessionLocal() as db:
            goal = db.get(Goal, command_goal_id)
            if not goal or str(goal.chat_id) != str(chat_id):
                await bot.send_message(chat_id=chat_id, text="Goal not found.")
                return {"ok": True}
            goal.status = "completed"
            db.commit()
            await bot.send_message(chat_id=chat_id, text=f"Goal completed: {goal.title}")
            return {"ok": True}

    if text_lower.startswith("/goal generate") or text_lower.startswith("/goal tasks") or "generate tasks" in text_lower:
        if command_goal_id is None:
            await bot.send_message(chat_id=chat_id, text="Usage: /goal generate <goal_id>")
            return {"ok": True}

        with SessionLocal() as db:
            goal = db.get(Goal, command_goal_id)
            if not goal or str(goal.chat_id) != str(chat_id):
                await bot.send_message(chat_id=chat_id, text="Goal not found.")
                return {"ok": True}

            try:
                task_list = generate_tasks_for_goal(goal)
            except Exception as exc:
                await bot.send_message(chat_id=chat_id, text=f"Task generation failed: {exc}")
                return {"ok": True}

            created_tasks = []
            for item in task_list[:4]:
                task = Task(
                    chat_id=str(chat_id),
                    task=item.get("task", "Unnamed task"),
                    priority=normalize_priority(item.get("priority", "medium")),
                    status="pending",
                    goal_id=goal.id,
                )
                db.add(task)
                created_tasks.append(task)
            db.commit()
            for task in created_tasks:
                db.refresh(task)

            if not created_tasks:
                await bot.send_message(chat_id=chat_id, text="No tasks could be generated for that goal.")
                return {"ok": True}

            lines = [f"{task.id}. {task.task} [{task.priority}]" for task in created_tasks]
            await bot.send_message(chat_id=chat_id, text="Generated tasks:\n" + "\n".join(lines))
            return {"ok": True}

    if text_lower.startswith("/goal") or text_lower.startswith("create goal") or text_lower.startswith("goal:") or text_lower.startswith("my goal"):
        raw_text = text
        if text_lower.startswith("/goal"):
            parts = text.split(" ", 2)
            if len(parts) >= 3 and parts[1] not in {"create", "list", "complete", "done", "generate", "tasks"}:
                raw_text = parts[2]
            elif len(parts) >= 2 and parts[1] == "create":
                raw_text = parts[2] if len(parts) > 2 else ""

        if not raw_text.strip():
            await bot.send_message(chat_id=chat_id, text="Please describe the goal you want to create.")
            return {"ok": True}

        try:
            goal_data = extract_goal(raw_text)
        except Exception as exc:
            await bot.send_message(chat_id=chat_id, text=f"Goal extraction failed: {exc}")
            return {"ok": True}

        if goal_data.get("not_goal"):
            await bot.send_message(chat_id=chat_id, text="I did not detect a goal in that message.")
            return {"ok": True}

        pending = build_pending_goal(goal_data)
        if pending["awaiting"]:
            chat_memory["pending_goal"] = pending
            save_memory(memory)
            await bot.send_message(chat_id=chat_id, text=goal_follow_up_prompt(pending["awaiting"][0]))
            return {"ok": True}

        with SessionLocal() as db:
            goal = create_goal(db, str(chat_id), goal_data)
            await bot.send_message(chat_id=chat_id, text=format_goal_summary(goal))
            return {"ok": True}

    if text_lower == "/tasks":
        with SessionLocal() as db:
            tasks = db.query(Task).filter(Task.chat_id == str(chat_id)).all()
        if not tasks:
            await bot.send_message(chat_id=chat_id, text="No tasks.")
            return {"ok": True}

        lines = [f"{task.id}. {task.task} [{task.status}]" for task in tasks]
        await bot.send_message(chat_id=chat_id, text="Your tasks:\n" + "\n".join(lines))
        return {"ok": True}

    if text_lower == "/done":
        await bot.send_message(chat_id=chat_id, text="Use /done <task_id> to mark a task completed.")
        return {"ok": True}

    if text_lower.startswith("/done"):
        try:
            task_id = int(text.split(" ")[1])
            with SessionLocal() as db:
                task = db.get(Task, task_id)
                if not task or str(task.chat_id) != str(chat_id):
                    await bot.send_message(chat_id=chat_id, text="Task not found.")
                    return {"ok": True}
                task.status = "completed"
                db.commit()
                await bot.send_message(chat_id=chat_id, text=f"Task {task_id} completed.")
                return {"ok": True}
        except Exception:
            await bot.send_message(chat_id=chat_id, text="Invalid command. Use /done <task_id>.")
            return {"ok": True}

    if text_lower == "/today":
        with SessionLocal() as db:
            tasks = db.query(Task).filter(Task.chat_id == str(chat_id), Task.status == "pending").all()
        if not tasks:
            await bot.send_message(chat_id=chat_id, text="No pending tasks.")
            return {"ok": True}
        plan = generate_today_plan(tasks)
        await bot.send_message(chat_id=chat_id, text=plan)
        return {"ok": True}

    try:
        task_data = extract_task(text)
    except Exception as exc:
        await bot.send_message(chat_id=chat_id, text="Could not extract a task from that message.")
        return {"ok": True}

    with SessionLocal() as db:
        task = Task(
            chat_id=str(chat_id),
            task=task_data.get("task", text),
            priority=normalize_priority(task_data.get("priority", "medium")),
            status="pending",
        )
        db.add(task)
        db.commit()
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"Task added:\n{task.task}\nPriority: {task.priority}"
            ),
        )

    return {"ok": True}

