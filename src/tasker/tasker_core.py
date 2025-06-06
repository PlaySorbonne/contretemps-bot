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
import pytz
from random import randint
import asyncio
from discord.ext import tasks
from discord import NotFound, HTTPException, Forbidden

from database.tasker import *
from database.base import ServerConnexion as Server
from database.tools import get_or_create
from utils import fetch_message_list_opt, fetch_message_opt, fetch_channel_opt
from utils import publish_long_message
from database import engine
from bot import bot
from commands.interactions.tasker import TaskInteractView
from template import parser as template_parser
from lark.exceptions import UnexpectedInput

from tasker.tasker_pretty import *

#TODO TODO : split this into two parts: an interface + a core
#            the interface does validations, and calls the core
#TODO custom timedelta dates type in sqlalchemy
#TODO reminder frequency better granurarity (now just in days)

def _get_project(s, guild_id, project_name):
  return (s.scalars(select(Project)
          .filter_by(project_name=project_name, server_id=str(guild_id)))
          .first())

def set_timezone(guild_id, timezone):
  with Session(engine) as s, s.begin():
    server = get_or_create(s, Server, server_id=str(guild_id))
    server.timezone = timezone

def roll_reminder_time(freq, rho=.5):
  now = datetime.utcnow()
  then = now+timedelta(seconds=int(freq))
  choices = then.timestamp() - now.timestamp()
  choose = randint(rho*choices, choices)
  return (now+timedelta(seconds=choose)).isoformat()

async def create_empty_messages(channel, n=10):
  message_creations = (channel.send(content='\u200E') for _ in range(n))
  desc_message = await asyncio.gather(*message_creations)
  desc_message.sort(key=lambda x: x.created_at)
  return desc_message

class BadTemplateFormat(Exception):
  pass
class TemplateInterpreterError(Exception):
  pass



async def create_project(guild, name, forum, category, who):
  with Session(engine) as s, s.begin():
    guild_object = get_or_create(s, Server, server_id=str(guild.id))
    #forum = await guild.create_forum_channel(name=name, category=category
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

def get_project_tasks(guild_id, project_name):
  with Session(engine) as s:
    p = _get_project(s, guild_id, project_name)
    if p is not None:
      return [t.title for t in p.tasks]
    return []

def is_project_admin(user, guild, project):
  with Session(engine) as s:
    p = _get_project(s, guild.id, project)
    admins = [a.admin_id for a in p.admins]
    u = bot.get_guild(guild.id).get_member(user.id)
    return u is not None and (
      str(u.id) in admins or
      any(str(role.id) in admins for role in u.roles)
    )

async def check_forum_permissions(guild_id, project):
  with Session(engine) as s:
    p = _get_project(s, guild_id, project)
    try:
      forum = await bot.fetch_channel(int(p.forum_id)) #TODO forum might be NULL.
      perms = forum.permissions_for(forum.guild.get_member(bot.user.id))
      return perms.send_messages and perms.manage_threads and perms.send_messages_in_threads
    except Forbidden:
      return False

def set_project_admin(guild_id, project_name, user_id, to):
  with Session(engine) as s, s.begin():
    p = _get_project(s, guild_id, project_name)
    admin = get_or_create(s, ProjectAdmin,
                         project_id=p.project_id, admin_id=str(user_id))
    if to:
      p.admins.append(admin)
    elif admin in p.admins:
      try : s.delete(admin)
      except ValueError: pass

def get_project_admins(guild_id, project_name):
  with Session(engine) as s:
    p = _get_project(s, guild_id, project_name)
    return [a.admin_id for a in p.admins]

def remove_reminder(guild_id, project_name):
  with Session(engine) as s, s.begin():
    project = _get_project(s,guild_id, project_name)
    project.reminder_frequency = None
    for task in project.tasks:
      task.next_recall = None

def set_reminder(guild_id, project_name, reminder, template=None):
  with Session(engine) as s, s.begin():
    project = _get_project(s, guild_id, project_name)
    project.reminder_frequency = int(reminder.total_seconds())
    project.reminder_template = template
    now = datetime.utcnow()
    then = now + reminder
    choices = int(then.timestamp() - now.timestamp())
    for task in project.tasks:
      random_wait = randint(1, choices)
      task.next_recall = (now + timedelta(seconds=random_wait)).isoformat()
def set_reminder_template(guild_id, project_name, template):
  with Session(engine) as s, s.begin():
    project = _get_project(s, guild_id, project_name)
    project.reminder_template = template

def add_project_role(guild_id, project_name, role):
  with Session(engine) as s, s.begin():
    proj = _get_project(s, guild_id, project_name)
    roles = set(proj.project_roles.split(';')) - {''}
    roles.add(role)
    proj.project_roles = ';'.join(roles)
def remove_project_role(guild_id, project_name, role):
  with Session(engine) as s, s.begin():
    proj = _get_project(s, guild_id, project_name)
    roles = set(proj.project_roles.split(';'))
    roles.discard(role)
    proj.project_roles = ';'.join(roles)

@tasks.loop(seconds=300)
async def check_role_members():
  with Session(engine) as s, s.begin():
    projects = s.scalars(select(Project))
    for p in projects:
      roles = set(p.project_roles.split(';')) - {''}
      guild = await bot.fetch_guild(int(p.server_id))
      guild_members = [m async for m in guild.fetch_members()]
      all_roles = await guild.fetch_roles()
      for r in all_roles:
        if r.mention in roles:
          for m in (m for m in guild_members if r in m.roles):
            participant = get_or_create(
              s, Contributor,
              member_id=m.id, project_id=p.project_id
            )

class TaskAlreadyExists(Exception):
  pass
async def create_task(guild_id, project_name, task, s=None, upd=True):
  if s is None:
   with Session(engine) as s, s.begin():
    return await create_task(guild_id, project_name, task, s)
  proj = _get_project(s, guild_id, project_name)
  if s.scalars(
    select(Task).filter_by(project_id=proj.project_id, title=task.title)
  ).first() is not None:
    raise TaskAlreadyExists(task.title)
  #TODO : insert and commit before publishing messages
  proj.tasks.append(task)
  forum = await bot.fetch_channel(int(proj.forum_id))
  thread = await forum.create_thread(name=task.title, content='placeholder')
  desc_message = await create_empty_messages(thread,n=1)
  task.main_message_id = str(thread.starting_message.id)
  task.sec_message_id = ';'.join(str(x.id) for x in desc_message)
  task.thread_id = str(thread.id)
  if proj.reminder_frequency:
    now = datetime.utcnow()
    end = now + timedelta(seconds=int(proj.reminder_frequency))
    choices = int(end.timestamp()-now.timestamp())
    checkpoint = (now+timedelta(seconds=randint(choices/2, choices)))
    task.next_recall = checkpoint.isoformat()
  c_alerts = s.scalars(select(ProjectAlert).
                       filter_by(kind=ProjectAlert.ON_CREATE)
  )
  for alert in c_alerts:
    msg = make_task_change_message(task, s, 'create', alert.template)
    channel = await bot.fetch_channel(str(alert.channel_id))
    await channel.send(**msg)
    
  if upd:
    await update_task_messages(task, s, thread.starting_message, desc_message[0]) #TODO handle multiple messages
  return thread

class TaskDoesNotExist(Exception):
  pass
async def delete_task(guild_id, project_name, task_title, del_thread=False):
  with Session(engine) as s, s.begin():
    proj = _get_project(s, guild_id, project_name)
    task = s.scalars(
      select(Task).filter_by(project_id = proj.project_id, title=task_title)
    ).first()
    if task is None:
      raise TaskDoesNotExist()
    await delete_task_internal(task, s, del_thread)

async def delete_task_internal(task, s, del_thread):
  if del_thread:
    try:
      thread = await bot.fetch_channel(int(task.thread_id))
      await thread.delete()
    except NotFound: pass
    except Forbidden: pass
    except HTTPException: pass
    #TODO: handle these exceptions and signal to user
  s.delete(task)

async def edit_task_description(task, description, s=None):
  if s is None:
   with Session(engine) as s, s.begin():
    s.add(task)
    return await edit_task_description(task, description, s)
  task.description = description
  await update_task_messages(task, s)

class NameAlreadyExists(Exception):
  pass
async def edit_task_title(guild_id, project_name, task_title, new_title):
  with Session(engine) as s, s.begin():
    proj = _get_project(s, guild_id, project_name)
    task = s.scalars(
      select(Task).filter_by(project_id = proj.project_id, title=task_title)).first()
    if task is None:
      raise TaskDoesNotExist()
    await edit_task_title_internal(task, new_title, s)

async def edit_task_title_internal(task, new_title, s=None):
  if s is None:
    with Session(engine) as s, s.begin():
      s.add(task)
      return await edit_task_title_internal(task, new_title, s)
  # TODO : Check name does not already exists and raise otherwise
  task.title = new_title
  await update_task_thread_title(task, s)

async def update_task_thread_title(task, s=None):
  if s is None:
    with Session(engine) as s, s.begin():
      s.add(task)
      return await update_task_thread_title(task, s)
  thread = await bot.fetch_channel(int(task.thread_id))
  if thread.archived:
    await thread.unarchive()
  await thread.edit(name=task.title)

async def update_task_messages(task, s=None, main=None, sec=None):
  if s is None:
   with Session(engine) as s, s.begin():
    s.add(task)
    return await update_task_messages(task, s, main, sec)
  main_message_components = make_main_task_message(task, s)
  sec_message_components = make_sec_task_message(task, s)
  #await await main.edit(**main_message_components)
  new_messages = await publish_long_message(task.main_message_id, task.thread_id, main_message_components)
  task.main_message_id = new_messages
  task.sec_message_id = await publish_long_message(
    task.sec_message_id,
    task.thread_id,
    sec_message_components
  )

async def update_all_tasks_messages(server_id, project_name, s=None):
  if s is None:
    with Session(engine) as s, s.begin():
      return await update_all_tasks_messages(server_id, project_name, s=s)
  p = _get_project(s, server_id, project_name)
  for task in p.tasks:
    await update_task_messages(task, s)

async def bulk_create_tasks(guild_id, project_name, tasks):
  with Session(engine, autoflush=False) as s, s.begin():
    p = _get_project(s, guild_id, project_name)
    for t in tasks:
      if s.scalars(
        select(Task).filter_by(project_id=p.project_id, title=t.title)
      ).first() is not None:
        raise TaskAlreadyExists(t.title)
    for task in tasks:
      await create_task(guild_id, project_name, task, s, upd=True)
    s.flush()
    if p.main_thread:
      await update_main_thread(p, s)

async def update_task_of(thread):
  with Session(engine) as s, s.begin():
    task = find_task_by_thread(thread, s)
    await update_task_messages(task, s)

async def update_advancement(task, advancement, s):
  task.advancement = advancement
  await update_task_messages(task, s)
  if advancement >= 100:
    for alert in task.project.alerts:
      if alert.kind == ProjectAlert.ON_COMPLETE:
        message = make_task_change_message(
          task, s, 'complete', alert.template
        )
        channel = await fetch_channel_opt(alert.channel_id)
        await channel.send(**message) #TODO message too long
    for task2 in task.successors:
      if all(k.advancement >= 100 for k in task.predecessors):
        await update_task_messages(task2, s)

async def has_main_thread(guild_id, project_name):
  with Session(engine) as s, s.begin():
    p = _get_project(s, guild_id, project_name)
    t = p.main_thread
    try:
      thread = await bot.fetch_channel(int(t)) if t else None
    except NotFound:
      p.main_thread = None
      return None
    return thread

async def publish_main_thread(
  guild_id,
  project_name,
  title,
  main_template=None,
  sec_template=None
):
  with Session(engine) as s, s.begin():
    proj = _get_project(s, guild_id, project_name)
    forum = await bot.fetch_channel(int(proj.forum_id))
    thread = await has_main_thread(guild_id, project_name)
    if thread:
      message = proj.main_message
      sec_messages = [await thread.fetch_message(int(x)) for x in proj.sec_messages.split(';')]
      await thread.edit(name=title)
    else:
      thread = proj.main_thread or await forum.create_thread(name=title, content='placeholder')
      message = thread.starting_message.id
      sec_messages = await create_empty_messages(thread,n=1)
    await thread.edit(pinned=True)
    message = await thread.fetch_message(int(message))
    proj.main_thread = str(thread.id)
    proj.main_template=None
    proj.sec_template=None
    proj.main_message = str(message.id)
    proj.sec_messages = ';'.join(str(x.id) for x in sec_messages)
    await update_main_thread(proj, s, thread, message, sec_messages)
    return thread
    
async def remove_main_thread(
  guild_id,
  project_name,
  delete=False
):
  with Session(engine) as s, s.begin():
    proj = _get_project(s, guild_id, project_name)
    if proj.main_thread:
      if delete:
        try:
          t = await bot.fetch_channel(int(proj.main_thread))
          await t.delete()
        except NotFound:
          pass
      proj.main_thread = proj.main_message = proj.sec_messages = None
      proj.main_template = proj.sec_template = None

async def update_main_thread(
  proj,
  s=None,
  thread=None,
  main_message=None,
  sec_messages=None
):
  if s is None:
    with Session(engine) as s, s.begin():
      return await update_main_thread(
        proj, s,thread, main_message, sec_messages
      )
  msg = make_main_thread_message(proj, s)
  msg2 = make_sec_thread_message(proj, s)
  #await main_message.edit(**msg)
  proj.main_message = await publish_long_message(
    proj.main_message,
    proj.main_thread,
    msg
  )
  proj.sec_messages = await publish_long_message(
    proj.sec_messages,
    proj.main_thread,
    msg2
  )
  #await sec_messages[0].edit(**msg2)

async def update_main_thread_of(project_name, guild_id):
  with Session(engine) as s, s.begin():
    proj = _get_project(s, str(guild_id), project_name)
    await update_main_thread(proj, s)

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
  if task in contributor.tasks(Kind):
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
  await update_task_secondary_message(task, s)

async def delete_step(step_id):
 with Session(engine) as s, s.begin():
   step = s.get(TaskStep, step_id)
   if step:
     task = step.task
     s.delete(step)
     await update_task_messages(task, s)

async def edit_step_number(step_id, newnum):
 with Session(engine) as s, s.begin():
   step = s.get(TaskStep, step_id)
   if step:
     step.step_number = newnum
     await update_task_messages(step.task, s)

async def check_step(step_id):
 with Session(engine) as s, s.begin():
   step = s.get(TaskStep, step_id)
   if step:
     step.done = int(not step.done)
     await update_task_messages(step.task, s)

async def update_task_secondary_message(task,s):
  #TODO : handle long messages
  msg = make_sec_task_message(task, s)
  task.sec_message_id = await publish_long_message(
    task.sec_message_id,
    task.thread_id,
    msg
  )

def is_task_thread(thread_id):
  return find_task_by_thread(thread_id) is not None

async def add_step(thread_id, description, n, kind):
 with Session(engine) as s, s.begin():
   task = find_task_by_thread(thread_id, s)
   task.steps.append(TaskStep(
    step_description=description,
    step_number=n,
    kind=kind
   ))
   await update_task_messages(task, s)

async def add_dependency(thread_1, thread_2):
 with Session(engine) as s, s.begin():
   t1 = find_task_by_thread(thread_1, s)
   t2 = find_task_by_thread(thread_2, s)
   if t2 is None or t1 is None: return
   # the None check here won't be necessary once concurrency is handled
   if t2 not in t1.predecessors:
     t1.predecessors.append(t2)
   else:
     t1.predecessors.remove(t2)
   await update_task_messages(t1, s) 

async def edit_log_message(log_key, new_message):
  with Session(engine) as s, s.begin():
    log = s.get(TaskLog, log_key)
    if log:
      log.log_message = new_message
    await update_task_secondary_message(log.task, s)
async def delete_log_message(log_key):
  with Session(engine) as s, s.begin():
    log = s.get(TaskLog, log_key)
    if log:
      s.delete(log)
    await update_task_secondary_message(log.task, s)

def create_project_alert(
  guild_id, project_name, channel_id,
  alert_id, kind, freq=None, template=None, start=None
):
  with Session(engine) as s, s.begin():
    proj = _get_project(s, guild_id, project_name)
    alert = ProjectAlert(
      alert_id=alert_id, kind=kind, channel_id=channel_id,
      frequency=int(freq.total_seconds()) if freq else None, template=template
    )
    if start:
      alert.start = start.utcformat()
    proj.alerts.append(alert)

async def validate_template(guild_id, project_name, template, context=None):
  with Session(engine) as s:
    project = _get_project(s, guild_id, project_name)
    try:
      res = template_parser.parse(template)
    except UnexpectedInput as e:
      raise BadTemplateFormat(e.get_context(template))
    return
    #TODO: try to load the template (like execute the msg generating function, without the message publishing function, and return the message to the caller)
    #TODO: actually maybe just replace this function alltogether with the message generating function, that either generates the message or throws the appropriate exceptions!

def contributor_summary_message(guild_id, project_name, contributor_id):
  with Session(engine) as s:
    p = _get_project(s, guild_id, project_name)
    c = s.get(Contributor, (str(contributor_id), p.project_id))
    if c is not None:
      return make_personnal_summary_message(p, c, s)
    return {'content': 'Vous ne faites pas partie de ce projet.'}

def project_contributors_stats(guild_id, project_name):
  with Session(engine) as s:
    p = _get_project(s, guild_id, project_name)
    return make_contributor_stats_message(p, s)

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
         contents = make_reminder_message(
           task, active, s,
           project.reminder_template
         )
         await user.send(**contents)
       last = now + timedelta(seconds=int(project.reminder_frequency))
       choices = (last.timestamp() - now.timestamp())
       new_checkpoint = now + timedelta(seconds=randint(choices//2, choices))
       task.next_recall = new_checkpoint.isoformat()

@tasks.loop(seconds=10)
async def do_frequent_alerts():
  with Session(engine) as s, s.begin():
    alerts = s.scalars(select(ProjectAlert)
                       .where(ProjectAlert.kind == ProjectAlert.FREQUENT)
    )
    async def send_alert(s, l, a):
      channel = await bot.fetch_channel(str(a.channel_id))#TODO safely
      alert_message = make_frequent_alert_message(
        a.project, l, s, a.template
      )
      await channel.send(**alert_message)
    for alert in alerts:
      if alert.last_update is None:
        alert.last_update = datetime.utcnow()
        await send_alert(s, None, alert)
      else:
        last = datetime.fromisoformat(alert.last_update)
        last =  pytz.timezone(alert.project.server.timezone).localize(last)
        nxt = last + timedelta(seconds=int(alert.frequency))
        now = pytz.UTC.localize(datetime.utcnow())
        if now >= nxt:
          last2=last
          while last2+timedelta(seconds=int(alert.frequency)) < now:
            last2+=timedelta(seconds=int(alert.frequency))
          alert.last_update = last2.replace(tzinfo=None)
          await send_alert(s, last.replace(tzinfo=None), alert)

async def update_all_tasks_messages(server_id, project_name, s=None):
  if s is None:
    with Session(engine) as s, s.begin():
      return await update_all_tasks_messages(server_id, project_name, s=s)
  p = _get_project(s, server_id, project_name)
  for task in p.tasks:
    await update_task_messages(task, s)


do_reminders.start()
do_frequent_alerts.start()
check_role_members.start()
