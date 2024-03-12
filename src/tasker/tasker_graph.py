


from sqlalchemy.orm import Session
from database import engine


def all_codependencies(task, s=None):
  if s is None:
    with Session(engine) as s:
      return all_dependencies(task, s)
  to_visit = [task]
  visited = {task}
  while to_visit:
    u = to_visit.pop()
    for v in u.successors:
      if v not in visited:
        to_visit.append(v)
        visited.add(v)
  return visited
