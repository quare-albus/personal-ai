from sqlalchemy import Column, Integer, String
from database import Base

class Task(Base):

    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)

    chat_id = Column(String)

    task = Column(String)

    priority = Column(String)

    status = Column(String)