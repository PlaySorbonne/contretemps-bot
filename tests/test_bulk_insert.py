

from src.database.tasker import Task, TaskStep, TaskLog, TaskDependency
from src.tasker.task_text_input import tasks_parser

parsed = tasks_parser.parse(open('./tests/bulk_insert.tasks').read())
transformed = parsed
print(transformed)

from sqlalchemy.orm import Session
from database.tasker import *
from sqlalchemy import select, create_engine
from database.base import *

engine = create_engine("sqlite:///", echo=False)
Base.metadata.create_all(engine)
with Session(engine) as ss, ss.begin():
  s = ServerConnexion(server_id = "hehe")
  p = Project()
  p.project_id = 5
  p.project_name = "myproject"
  s.projects.append(p)
  for task in transformed:
    p.tasks.append(task)
  ss.add(s)
with Session(engine) as s,s.begin():
  print(s.get(Project, 5).tasks[0].successors)
  print(s.get(Project, 5).tasks[1].steps)
