from main import get_active_goals, get_recent_reflections, get_recent_tasks
from models import Task

def build_context(user_id):

    goals = get_active_goals(user_id)

    reflections = get_recent_reflections(user_id)

    tasks = get_recent_tasks(user_id)

    context = ""

    context += format_goals(goals)

    context += format_reflections(reflections)

    context += format_tasks(tasks)

    return context

def format_goals(goals):

    return [
        {
            "title": goal.title,
            "priority": goal.priority,
            "status": goal.status,
            "progress": goal.progress,
            "health_score": goal.health_score
        }
        for goal in goals
    ]

def format_reflections(reflections):

    return [
        {
            "goal_id": reflection.goal_id,
            "reflection": reflection.reflection_text,
            "blockers": reflection.blockers,
            "emotional_state": reflection.emotional_state,
            "energy_level": reflection.energy_level,
            "productivity_score":
                reflection.productivity_score,
            "progress_score":
                reflection.progress_score,
            "created_at":
                reflection.created_at.isoformat()
        }
        for reflection in reflections
    ]

def format_tasks(tasks):

    return [
        {
            "title": task.title,
            "priority": task.priority,
            "completed": task.completed
        }
        for task in tasks
    ]


def get_active_goals(user_id):

    db = SessionLocal()

    goals = (
        db.query(Goal)
        .filter(
            Goal.user_id == user_id,
            Goal.status == "ACTIVE"
        )
        .order_by(desc(Goal.priority))
        .all()
    )

    db.close()

    return goals

def get_recent_reflections(
    user_id,
    limit=5
):

    db = SessionLocal()

    reflections = (
        db.query(Reflection)
        .filter(
            Reflection.user_id == user_id
        )
        .order_by(
            desc(Reflection.created_at)
        )
        .limit(limit)
        .all()
    )

    db.close()

    return reflections

def get_recent_tasks(
    user_id,
    limit=10
):

    db = SessionLocal()

    tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user_id
        )
        .order_by(
            Task.completed.asc(),
            desc(Task.priority)
        )
        .limit(limit)
        .all()
    )

    db.close()

    return tasks
