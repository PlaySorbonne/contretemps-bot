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
from commands.interactions.tasker import ChooseTaskView

#TODO custom timedelta dates type in sqlalchemy
#TODO reminder frequency better granurarity (now just in days)

def _get_project(s, guild_id, project_name):
  return (s.scalars(select(Project)
          .filter_by(project_name=project_name, server_id=guild_id))
          .one())

async def create_project(guild, name, category):
  with Session(engine) as s, s.begin():
    guild_object = get_or_create(s, Server, server_id=str(guild.id))
    forum = await guild.create_forum_channel(name=name, category=category)
    new_project = Project(forum_id = str(forum.id), project_name=name)
    guild_object.projects.append(new_project)
    return new_project, forum

def get_guild_projects(guild_id):
  with Session(engine) as s, s.begin():
    guild_obj = get_or_create(s, Server, server_id=guild_id)
    return [proj.project_name for proj in guild_obj.projects]

def check_project_exists(guild_id, project_name):
  with Session(engine) as s:
    return None is not _get_project(s, guild_id, project_name)

def remove_reminder(guild_id, project_name):
  with Session(engine) as s, s.begin():
    project = _get_project(s,guild_id, project_name)
    project.reminder_frequency = None
    for task in project.tasks:
      task.next_recall = None

def set_reminder(guild_id, project_name, reminder):
  with Session(engine) as s, s.begin():
    project = _get_project(s, guild_id, project_name)
    project.reminder_frequency = reminder
    now = datetime.utcnow()
    then = now + timedelta(days=reminder)
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

async def create_task(guild_id, project_name, task, s=None):
  if s is None:
   with Session(engine) as s, s.begin():
    return await create_task(guild_id, project_name, task, s)
  proj = _get_project(s, guild_id, project_name) #TODO : insert and commit before publishing messages 
  forum = await bot.fetch_channel(int(proj.forum_id))
  thread = await forum.create_thread(name=task.title, content='placeholder')
  desc_message = await thread.send(content='placeholder')
  task.main_message_id = str(thread.starting_message.id)
  task.sec_message_id = str(desc_message.id)
  task.thread_id = str(thread.id)
  if proj.reminder_frequency:
    now = datetime.utcnow()
    end = now + timedelta(days=proj.reminder_frequency)
    choices = int(end.timestamp()-now.timestamp())
    checkpoint = (now+timedelta(seconds=randint(choices/2, choices)))
    task.next_recall = checkpoint.isoformat()
    
  proj.tasks.append(task)
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
    for task in tasks:
      await create_task(guild_id, project_name, task, s)

def find_task_by_thread(thread_id, s=None):
  if s is None:
   with Session(engine) as s, s.begin():
    return find_task_by_thread(thread_id, s)
  task = s.scalars(select(Task).filter_by(thread_id=thread_id))
  return task.first()

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
       last = now + timedelta(days=int(project.reminder_frequency))
       choices = (last.timestamp() - now.timestamp())
       new_checkpoint = now + timedelta(seconds=randint(choices/2, choices))
       task.next_recall = new_checkpoint.isoformat()

        

def make_main_task_message(task, s):
  return {'content': 'TODO: MAIN TASK MESSSAGE AND STUFF', 'view':ChooseTaskView()}
def make_sec_task_message(task, s):
  return {'content': 'TODO: SECONDARY TASK MESSAGE AND STUFF'}
def make_reminder_message(task, user, s):
  return {'content': 'TODO: PRIVATE REMINDER MESSAGE !'}

do_reminders.start()
