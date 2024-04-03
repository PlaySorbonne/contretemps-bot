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

from datetime import datetime
import pytz
isotodt = datetime.fromisoformat
from random import randint
from sqlalchemy import select

from database.tasker import *
from template import Engine, parser
from commands.interactions.tasker import TaskInteractView


def idt(iso, tz): #TODO this goes to utils.py and gets a better name
  ret = datetime.fromisoformat(iso)
  return pytz.timezone(tz).localize(ret)

common_generic_context = {
  'less_than': (lambda a, b: a <= b),
  'and': (lambda a, b: a and b),
  'not': (lambda t: not t),
  'eq': (lambda u, v: u == v),
  'truncate': (lambda s, n: s[:n]),
  'length': len,
  'roll_dice': randint,
  'now': (lambda : datetime.utcnow()),
  'full_date': (lambda d: f'<t:{int(d.timestamp())}:F>' if d else "(Pas de date)"),
  'relative_date': (lambda d: f'<t:{int(d.timestamp())}:R>' if d else "(Pas de date)"),
  'last_of': (lambda l: l[-1] if len(l) else None),
  'first_of': (lambda l: l[0] if len(l) else None),
  'range': range
}

def make_common_project_context(s):
  def ulog_select(task):
    return select(TaskLog).filter_by(
      project_id=task.project_id,
      task_title=task.title,
      log_type=TaskLog.USER_LOG
    ).order_by(TaskLog.timestamp)
  common_context = {
    'project_tasks': (lambda p: p.tasks),
    'project_unfinished_tasks':
      (lambda p: [t for t in p.tasks if t.advancement <= 100]),
    'task_finished': (lambda t: t.advancement >= 100),
    'task_name': (lambda t: t.title),
    'task_thread': (lambda t: f'<#{t.thread_id}>'),
    'task_sub_steps':
      (lambda t: 
        sorted(
          [x for x in t.steps if x.kind == TaskStep.SUBTASK],
          key=lambda x : x.step_number
        )
      ),
    'task_remark_steps':
      (lambda t: [x for x in t.steps if x.kind == TaskStep.REMARK]),
    'task_all_steps': (lambda t: t.steps),
    'task_unfinished_steps':
      (lambda t: [x for x in t.steps if not x.done and x.kind==TaskStep.SUBTASK]),
    'task_percentage': (lambda t: (t.advancement or 0)),
    'task_description': (lambda t: t.description),
    'task_start': (lambda t: isotodt(t.starts_after)if t.starts_after else None),
    'task_end': (lambda t: isotodt(t.ends_before) if t.ends_before else None),
    'task_urgent': 
      (lambda t: t.ugent_after and isotodt(t.urgent_after)<datetime.utcnow()),
    'predecessors': (lambda t: t.predecessors),
    'unfinished_predecessors':
      (lambda t: [x for x in t.predecessors if x.advancement >=100]),
    'successors': (lambda t: t.successors),
    'step_desc': (lambda s: s.step_description),
    'step_number': (lambda s: s.step_number),
    'step_done': (lambda s: s.done),
    'task_logs': (lambda t: list(s.scalars(ulog_select(t)))),
    'task_user_logs':
      (lambda t,u: list(s.scalars(ulog_select(t).filter_by(member_id=u.member_id)))),
    'log_date': (lambda log: 
      idt(log.timestamp, log.task.project.server.timezone) if log else None
     ),
    'log_message': (lambda log: log.log_message),
    'log_author': 
      (lambda log: s.get(Contributor, (log.member_id, log.project_id))),
    'user_mention': (lambda u: f'<@{u.member_id}>'),
    'participants': (lambda t: t.active),
    'interested': (lambda t: t.interested),
    'veterans':(lambda t:t.veterans),
  }
  return common_context

def make_global_project_context(s, p):
  context = {
    'project_name': p.project_name,
    'project_forum': f'<#p.forum_id>',
    'project_main_thread': f'<#p.main_thread>',
    'all_tasks': p.tasks,
    'unfinished_tasks':[t for t in p.tasks if t.advancement<100],
    'finished_tasks': [t for t in p.tasks if t.advancement>=100],
    'project_contributors' : p.contributors,
    'project_admins' : [x for x in p.contributors if x.project_admin]
  }
  return context

def make_reminder_message(task, user, s, template=None):
  context = {
    'task': task,
    'reminded_user': user,
  } | make_common_project_context(s) | common_generic_context
  if template is None:
    template=open('./src/ressources/default_reminder.template').read()
  engine = Engine(context)
  result_message = engine.visit(parser.parse(template))
  return {'content': result_message}


def make_main_task_message(task, s):
  context = {
    'task': task,
  } | make_common_project_context(s) | common_generic_context
  main = open('./src/ressources/default_task_main.template').read()
  engine = Engine(context)
  return {'content': engine.visit(parser.parse(main)), 'view': TaskInteractView() }

def make_sec_task_message(task, s):
  context = {
    'task': task,
  } | make_common_project_context(s) | common_generic_context
  sec = open('./src/ressources/default_task_sec.template').read()
  engine = Engine(context)
  return {'content': engine.visit(parser.parse(sec))}

def make_frequent_alert_message(project, last, s, template=None):
  context = (
    make_common_project_context(s) | 
    common_generic_context |
    make_global_project_context(s, project)
  )
  if template is None:
    template = open('./src/ressources/default_frequent_alert.template').read()
  engine = Engine(context)
  return {'content': engine.visit(parser.parse(template))}

def make_task_change_message(task, s, what, template=None):
  context = {
    'task' : task,
    'project_name': task.project,
  } | make_common_project_context(s) | common_generic_context
  if template is None:
    template = open(f'./src/ressources/default_{what}_alert.template').read()
  engine = Engine(context)
  return {'content': engine.visit(parser.parse(template)) }

def make_main_thread_message(project, s, template=None):
  context = (
    make_common_project_context(s) | 
    common_generic_context |
    make_global_project_context(s, project)
  )
  if template is None:
    template = open('./src/ressources/default_project_main_message.template').read()
  engine = Engine(context)
  return {'content': engine.visit(parser.parse(template))}

def make_sec_thread_message(project, s, template=None):
  context = (
    make_common_project_context(s) | 
    common_generic_context |
    make_global_project_context(s, project)
  )
  if template is None:
    template = open('./src/ressources/default_project_sec_message.template').read()
  engine = Engine(context)
  return {'content': engine.visit(parser.parse(template))}
