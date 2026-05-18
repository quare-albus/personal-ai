from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship
from database import Base


class Task(Base):

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String, index=True, nullable=False)
    task = Column(String, nullable=False)
    priority = Column(String, nullable=False, default="medium")
    status = Column(String, nullable=False, default="pending")
    goal_id = Column(Integer, ForeignKey("goals.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    goal = relationship("Goal", back_populates="tasks")


class Goal(Base):
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True)
    chat_id = Column(String, index=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    why = Column(Text, nullable=True)
    category = Column(String, nullable=True)
    priority = Column(String, nullable=False, default="medium")
    status = Column(String, nullable=False, default="active")
    progress = Column(Integer, nullable=False, default=0)
    health_score = Column(Integer, nullable=False, default=100)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tasks = relationship("Task", back_populates="goal", cascade="all, delete-orphan")

class Reflection(Base):
    __tablename__ = "reflections"

    id = Column(Integer, primary_key=True, autoincrement=True)

    user_id = Column(Integer, nullable=False)

    goal_id = Column(Integer, ForeignKey("goals.id"))

    reflection_text = Column(Text)

    blockers = Column(Text)

    emotional_state = Column(String)

    energy_level = Column(Integer)

    productivity_score = Column(Integer)

    progress_score = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)