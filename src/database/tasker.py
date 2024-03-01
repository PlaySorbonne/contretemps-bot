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
from sqlalchemy import ForeignKey as FK, ForeignKeyConstraint, CheckConstraint



class Project(Base):
    __tablename__ = 'project'
    
    project_id : Mapped[int] = mc(primary_key=True)
    project_name : Mapped[str]
    server_id = mc(FK(ServerConnexion.server_id))
    forum_id : Mapped[str]
    project_roles : Mapped[str]
    reminder_frequency : Mapped[str]
    
class Task(Base):
    __tablename__ = 'task'
    
    project_id : Mapped[int] = mc(FK(Project.project_id), primary_key=True)
    title : Mapped[str] = mc(primary_key=True)
    description : Mapped[str]
    starts_after : Mapped[NULL[str]]
    ends_before : Mapped[NULL[str]]
    urgent_after : Mapped[NULL[str]]
    ignore : Mapped[int]
    advancement : Mapped[int]
    next_recall : Mapped[NULL[str]]
    main_message_id : Mapped[str]
    sec_message_id : Mapped[str]

class Contributor(Base):
    __tablename__ = 'contributor'
    
    member_id : Mapped[str] = mc(primary_key=True)
    no_dms : Mapped[int]
    no_mention : Mapped[int]

class TaskLog(Base):
    __tablename__ = 'task_log'
    
    USER_LOG = 1
    SYSTEM_LOG = 2
    
    project_id : Mapped[int] = mc(primary_key=True)
    task_title : Mapped[str] = mc(primary_key=True)
    timestamp : Mapped[str] = mc(primary_key=True)
    log_message : Mapped[str]
    log_type : Mapped[int]
    member_id = mc(FK(Contributor.member_id))
    ForeignKeyConstraint([project_id, task_title],
                         [Task.project_id, Task.title])


class TaskStep(Base):
    __tablename__ = 'task_step'
    
    project_id : Mapped[int] = mc(primary_key=True)
    task_title : Mapped[str] = mc(primary_key=True)
    step_number : Mapped[int]
    step_description : Mapped[str]
    ForeignKeyConstraint([project_id, task_title],
                         [Task.project_id, Task.title])

class TaskDependency(Base):
    __tablename__ = 'task_dependency'
    
    pid1 : Mapped[int] = mc(primary_key=True)
    tid1 : Mapped[str] = mc(primary_key=True)
    t1 = ForeignKeyConstraint([pid1,tid1], [Task.project_id, Task.title])
    pid2 : Mapped[int] = mc(primary_key=True)
    tid2 : Mapped[str] = mc(primary_key=True)
    t2 = ForeignKeyConstraint([pid2,tid2], [Task.project_id, Task.title])
    check_project = CheckConstraint(pid1 == pid2)

class ContributorTaskMixin:
    project_id : Mapped[int] = mc(primary_key=True)
    task_title : Mapped[str] = mc(primary_key=True)
    member_id = mc(FK(Contributor.member_id), primary_key=True)
    ForeignKeyConstraint([project_id, task_title],
                         [Task.project_id, Task.title])   

class TaskParticipant(Base, ContributorTaskMixin):
    __tablename__ = 'task_participant'

class TaskInterested(Base, ContributorTaskMixin):
    __tablename__ = 'task_interested'

class TaskVeteran(Base, ContributorTaskMixin):
    __tablename__ = 'task_veteran'

     
