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

from typing import List, Optional as NULL
from .base import Base, ServerConnexion
from sqlalchemy.orm import Mapped, mapped_column as mc, relationship
from sqlalchemy import ForeignKey as FK, ForeignKeyConstraint, UniqueConstraint
from sqlalchemy import and_
from sqlalchemy.ext.declarative import declared_attr



class Project(Base):
    __tablename__ = 'project'
    
    project_id : Mapped[int] = mc(primary_key=True)
    project_name : Mapped[str]
    server_id = mc(FK(ServerConnexion.server_id))
    forum_id : Mapped[NULL[str]]
    project_roles : Mapped[str] = mc(default='')
    reminder_frequency : Mapped[NULL[str]]
    main_thread: Mapped[NULL[str]]
    main_message: Mapped[NULL[str]]
    sec_messages: Mapped[NULL[str]]
    main_template: Mapped[NULL[str]]
    sec_template: Mapped[NULL[str]]
    reminder_template: Mapped[NULL[str]]
    
    server : Mapped['ServerConnexion'] = relationship(back_populates='projects')
    tasks : Mapped[List['Task']] = relationship(back_populates='project')
    contributors : Mapped[List['Contributor']] = (
        relationship(back_populates='project'))
    
    UniqueConstraint("project_name", "server_id", name='project_name_unique')

class TaskDependency(Base):
    __tablename__ = 'task_dependency'
    
    project_id : Mapped[int] = mc(primary_key=True)
    task1 : Mapped[str] = mc(primary_key=True)
    task2 : Mapped[str] = mc(primary_key=True)
    t1 = ForeignKeyConstraint([project_id,task1],['task.project_id', 'task.title'])
    t2 = ForeignKeyConstraint([project_id,task2], ['task.project_id', 'task.title'])

class Task(Base):
    __tablename__ = 'task'
    
    project_id : Mapped[int] = mc(FK(Project.project_id), primary_key=True)
    title : Mapped[str] = mc(primary_key=True)
    description : Mapped[str] = mc(default='')
    starts_after : Mapped[NULL[str]]
    ends_before : Mapped[NULL[str]]
    urgent_after : Mapped[NULL[str]]
    ignore : Mapped[int] = mc(default=0)
    advancement : Mapped[int] = mc(default=0)
    next_recall : Mapped[NULL[str]]
    thread_id : Mapped[NULL[str]]
    main_message_id : Mapped[NULL[str]]
    sec_message_id : Mapped[NULL[str]]
    
    project : Mapped[Project] = relationship(back_populates='tasks')
    veterans : Mapped[List['Contributor']] = relationship(
        back_populates='mastered_tasks', secondary='task_veteran')
    interested : Mapped[List['Contributor']] = relationship(
        back_populates='interesting_tasks',
        secondary='task_interested')
    active : Mapped[List['Contributor']] = relationship(
        back_populates='current_tasks', secondary='task_participant')
    steps : Mapped[List['TaskStep']] = (
        relationship(order_by='TaskStep.step_number'))
    successors : Mapped[List['Task']] = relationship(
        secondary='task_dependency',
        primaryjoin=and_(title == TaskDependency.task1,project_id == TaskDependency.project_id),
        secondaryjoin=and_(title == TaskDependency.task2, project_id == TaskDependency.project_id),
        backref='predecessors')
    
    def __repr__(s):
      return f"Task(project={s.project_id}, title='{s.title}')"

class Contributor(Base):
    __tablename__ = 'contributor'
    
    member_id : Mapped[str] = mc(primary_key=True)
    project_id = mc(FK(Project.project_id), primary_key=True)
    no_dms : Mapped[int] = mc(default=0)
    no_mention : Mapped[int] = mc(default=0)
    project_admin : Mapped[int] = mc(default=0)
    
    project : Mapped[Project] = relationship(back_populates='contributors')
    mastered_tasks : Mapped[List[Task]] = relationship(
        back_populates='veterans', secondary='task_veteran')
    interesting_tasks : Mapped[List[Task]] = relationship(
        back_populates='interested', secondary='task_interested')
    current_tasks : Mapped[List[Task]] = relationship(
        back_populates='active', secondary='task_participant')
    
    def tasks(self, Kind):
      return { TaskInterested: self.interesting_tasks,
               TaskParticipant: self.current_tasks,
               TaskVeteran: self.mastered_tasks }[Kind]

class TaskLog(Base):
    __tablename__ = 'task_log'
    
    USER_LOG = 1
    SYSTEM_LOG = 2
    
    project_id : Mapped[int] = mc(primary_key=True)
    task_title : Mapped[str] = mc(primary_key=True)
    timestamp : Mapped[str] = mc(primary_key=True)
    member_id : Mapped[str] = mc(primary_key=True)
    log_message : Mapped[str]
    log_type : Mapped[int]
    ForeignKeyConstraint([project_id, task_title],
                         [Task.project_id, Task.title])
    ForeignKeyConstraint([project_id, member_id],
                         [Contributor.project_id, Contributor.member_id])

class TaskStep(Base):
    __tablename__ = 'task_step'
    
    SUBTASK, REMARK = 0,1
    
    step_id : Mapped[int] = mc(primary_key=True)
    project_id : Mapped[int] = mc()
    task_title : Mapped[str] = mc()
    step_number : Mapped[NULL[int]]
    step_description : Mapped[str]
    done : Mapped[NULL[int]]
    kind : Mapped[int]
    ForeignKeyConstraint([project_id, task_title],
                         [Task.project_id, Task.title])
    
    def __repr__(self):
      return f"TaskStep({self.project_id}, {self.step_description[:20]}-, ...)"


class ContributorTaskMixin:
    project_id : Mapped[int] = mc(primary_key=True)
    task_title : Mapped[str] = mc(primary_key=True)
    member_id : Mapped[str] = mc(primary_key=True)
    
    @declared_attr
    def task_fk(cls):
        return ForeignKeyConstraint([cls.project_id, cls.task_title],
                                    [Task.project_id, Task.title])
    @declared_attr
    def contributor_fk(cls):
      return ForeignKeyConstraint([cls.project_id, cls.member_id],
                               [Contributor.project_id, Contributor.member_id])

class TaskParticipant(ContributorTaskMixin, Base):
    __tablename__ = 'task_participant'

class TaskInterested(ContributorTaskMixin, Base):
    __tablename__ = 'task_interested'

class TaskVeteran(ContributorTaskMixin, Base):
    __tablename__ = 'task_veteran'

     
