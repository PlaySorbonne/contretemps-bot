# This file is part of ContretempsBot <https://github.com/PlaySorbonne/contretemps-bot>
# Copyright (C) 2023-present PLAY SORBONNE UNIVERSITE
# Copyright (C) 2023 DaBlumer
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, timedelta
from random import randint
from discord.ext import tasks

from database.tasker import *
from database.base import ServerConnexion as Server
from database.tools import get_or_create
from database import engine
from bot import bot
from commands.interactions.tasker import TaskInteractView

#TODO custom timedelta dates type in sqlalchemy
#TODO reminder frequency better granurarity (now just in days)

def _get_project(s, guild_id, project_name):
  return (s.scalars(select(Project)
          .filter_by(project_name=project_name, server_id=str(guild_id)))
          .first())

def roll_reminder_time(freq, rho=.5):
  now = datetime.utcnow()
  then = now+timedelta(seconds=int(freq))
  choices = then.timestamp() - now.timestamp()
  choose = randint(rho*choices, choices)
  return (now+timedelta(seconds=choose)).isoformat()

async def create_project(guild, name, category, who):
  with Session(engine) as s, s.begin():
    guild_object = get_or_create(s, Server, server_id=str(guild.id))
    forum = await guild.create_forum_channel(name=name, category=category)
    new_project = Project(forum_id = str(forum.id), project_name=name)
    guild_object.projects.append(new_project)
    user = Contributor(member_id=str(who), project_admin=1)
    new_project.contributors.append(user)
    return new_project, forum

def get_guild_projects(guild_id):
  with Session(engine) as s, s.begin():
    guild_obj = get_or_create(s, Server, server_id=guild_id)
    return [proj.project_name for proj in guild_obj.projects]

def check_project_exists(guild_id, project_name):
  with Session(engine) as s:
    return None is not _get_project(s, guild_id, project_name)

def is_project_admin(user_id, guild_id, project):
  with Session(engine) as s:
    p = _get_project(s, guild_id, project)
    u = s.get(Contributor, (str(user_id), p.project_id))
    return u is not None and u.project_admin 

def set_project_admin(guild_id, project_name, user_id, to):
  with Session(engine) as s, s.begin():
    p = _get_project(s, guild_id, project_name)
    user = get_or_create(s, Contributor,
                         project_id=p.project_id, member_id=str(user_id))
    user.project_admin = to
    p.contributors.append(user)

def remove_reminder(guild_id, project_name):
  with Session(engine) as s, s.begin():
    project = _get_project(s,guild_id, project_name)
    project.reminder_frequency = None
    for task in project.tasks:
      task.next_recall = None

def set_reminder(guild_id, project_name, reminder):
  with Session(engine) as s, s.begin():
    project = _get_project(s, guild_id, project_name)
    project.reminder_frequency = int(reminder.total_seconds())
    now = datetime.utcnow()
    then = now + reminder
    choices = int(then.timestamp() - now.timestamp())
    for task in project.tasks:
      random_wait = randint(1, choices)
      task.next_recall = (now + timedelta(seconds=random_wait)).isoformat()


def add_project_role(guild_id, project_name, role):
  with Session(engine) as s, s.begin():
    proj = _get_project(s, guild_id, project_name)
    roles = set(proj.project_roles.split(';'))
    roles.add(role)
    proj.project_roles = ';'.join(roles)
def remove_project_role(guild_id, project_name, role):
  with Session(engine) as s, s.begin():
    proj = _get_project(s, guild_id, project_name)
    roles = set(proj.project_roles.split(';'))
    roles.discard(role)
    proj.project_roles = ';'.join(roles)

class TaskAlreadyExists(Exception):
  pass
async def create_task(guild_id, project_name, task, s=None):
  if s is None:
   with Session(engine) as s, s.begin():
    return await create_task(guild_id, project_name, task, s)
  proj = _get_project(s, guild_id, project_name) #TODO : insert and commit before publishing messages 
  proj.tasks.append(task)
  forum = await bot.fetch_channel(int(proj.forum_id))
  thread = await forum.create_thread(name=task.title, content='placeholder')
  desc_message = await thread.send(content='placeholder')
  task.main_message_id = str(thread.starting_message.id)
  task.sec_message_id = str(desc_message.id)
  task.thread_id = str(thread.id)
  if proj.reminder_frequency:
    now = datetime.utcnow()
    end = now + timedelta(seconds=int(proj.reminder_frequency))
    choices = int(end.timestamp()-now.timestamp())
    checkpoint = (now+timedelta(seconds=randint(choices/2, choices)))
    task.next_recall = checkpoint.isoformat()
    
  await update_task_messages(task, s, thread.starting_message, desc_message)

async def update_task_messages(task, s=None, main=None, sec=None):
  if s is None:
   with Session(engine) as s, s.begin():
    s.add(task)
    return await update_task_messages(task, s, main, sec)
  if main is None: main = await (await bot.fetch_channel(int(task.thread_id))).fetch_message(int(task.main_message_id))
  if sec is None: sec = await (await bot.fetch_channel(int(task.thread_id))).fetch_message(int(task.sec_message_id))
  main_message_components = make_main_task_message(task, s)
  sec_message_components = make_sec_task_message(task, s)
  await main.edit(**main_message_components)
  await sec.edit(**sec_message_components)

async def bulk_create_tasks(guild_id, project_name, tasks):
  with Session(engine, autoflush=False) as s, s.begin():
    p = _get_project(s, guild_id, project_name)
    for t in tasks:
      if s.scalars(
        select(Task).filter_by(project_id=p.project_id, title=t.title)
      ).first() is not None:
        raise TaskAlreadyExists(t.title)
    for task in tasks:
      await create_task(guild_id, project_name, task, s)

def find_task_by_thread(thread_id, s=None):
  if s is None:
   with Session(engine) as s, s.begin():
    return find_task_by_thread(thread_id, s)
  task = s.scalars(select(Task).filter_by(thread_id=thread_id))
  return task.first()

def is_task_contributor(Kind, member_id, task, s=None):
  if s is None:
   with Session(engine) as s, s.begin():
    return is_task_contributor(Kind, member_id, task, s)
  return s.get(Kind, (task.project_id, task.title, str(member_id))) is not None

async def add_task_contributor(Kind, task, member_id, s=None): #TODO log new contributor
  if s is None:
   with Session(engine) as s, s.begin():
    return await add_task_contributor(Kind, task, member_id, s=s)
  contributor = get_or_create(s, Contributor, member_id=str(member_id), project_id=task.project_id)
  link = Kind(project_id=task.project_id, task_title=task.title, member_id=str(member_id))
  s.add(link)
  if (Kind is TaskParticipant):
    interested = s.get(TaskInterested, (task.project_id, task.title, str(member_id)))
    if interested is not None:
      s.delete(interested)
  await update_task_messages(task, s=s)

async def remove_task_contributor(Kind, task, member_id, s=None):
  if s is None:
   with Session(engine) as s, s.begin():
     s.add(task)
     return await remove_task_contributor(Kind, task, member_id, s=s)
  contributor = s.get(Contributor, (str(member_id), task.project_id))
  contributor.tasks(Kind).remove(task)
  await update_task_messages(task, s=s)

async def task_user_log(task, contributor, message, s):
  log = TaskLog(
    project_id=task.project_id,
    task_title=task.title,
    timestamp=datetime.utcnow().isoformat(),
    member_id=contributor.member_id,
    log_message=message,
    log_type = TaskLog.USER_LOG
  )
  freq = task.project.reminder_frequency
  if freq:
    task.next_recall = roll_reminder_time(freq)
  s.add(log)

@tasks.loop(seconds=10)#TODO : 60)
async def do_reminders():
 with Session(engine) as s, s.begin():
  projects = s.scalars(select(Project).where(Project.reminder_frequency != None))
  for project in projects:
    for task in project.tasks:
     now = datetime.utcnow()
     checkpoint = datetime.fromisoformat(task.next_recall)
     if task.advancement < 100 and now > checkpoint:
       for active in task.active:
         user = await bot.fetch_user(int(active.member_id))
         contents = make_reminder_message(task, active, s)
         await user.send(**contents)
       last = now + timedelta(seconds=int(project.reminder_frequency))
       choices = (last.timestamp() - now.timestamp())
       new_checkpoint = now + timedelta(seconds=randint(choices//2, choices))
       task.next_recall = new_checkpoint.isoformat()

        

def make_main_task_message(task, s):
  return {'content': 'TODO: MAIN TASK MESSSAGE AND STUFF', 'view':TaskInteractView()}
def make_sec_task_message(task, s):
  return {'content': 'TODO: SECONDARY TASK MESSAGE AND STUFF'}
def make_reminder_message(task, user, s):
  return {'content': 'TODO: PRIVATE REMINDER MESSAGE !'}

do_reminders.start()
