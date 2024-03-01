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
from sqlalchemy import ForeignKey as FK, ForeignKeyConstraint



class UserAccess(Base):
    __tablename__ = "user_access"
    
    
    server_id = mc(FK("server_connexion.server_id"), primary_key=True)
    thing_id: Mapped[str] = mc(primary_key=True)
    mention: Mapped[NULL[str]]
    access_level: Mapped[int]
    
    server: Mapped[ServerConnexion] = relationship(back_populates="access_rules")
    
    
class WatchedCalendar(Base):
    __tablename__ = "watched_calendar"
    
    server_id = mc(FK("server_connexion.server_id"), primary_key=True)
    watch_id: Mapped[str] = mc(primary_key=True)
    channel_id: Mapped[NULL[str]]
    filter: Mapped[NULL[str]]
    updates_new: Mapped[NULL[int]]
    updates_mod: Mapped[NULL[int]]
    updates_del: Mapped[NULL[int]]
    replace: Mapped[NULL[str]]
    calendar_id: Mapped[NULL[str]]
    calendar_name: Mapped[NULL[str]]
    
    server: Mapped[ServerConnexion] = relationship(back_populates="watches")
    
    summaries: Mapped[List['EventSummary']] = relationship(back_populates="watch")
    
    def __repr__(self):
        return (f"WatchedCalendar(server={self.server_id}, id={self.watch_id},"
                +f"calendar_name={self.calendar_name})")


class EventSummary(Base):
    __tablename__ = "event_summary"
    
    server_id: Mapped[str] = mc(primary_key=True)
    watch_id: Mapped[str] = mc(primary_key=True)
    summary_id: Mapped[str] = mc(primary_key=True)
    base_date: Mapped[NULL[str]]
    frequency: Mapped[NULL[str]]
    header: Mapped[str]
    message_id: Mapped[NULL[str]]
    
    ForeignKeyConstraint([server_id, watch_id], 
                         [WatchedCalendar.server_id, WatchedCalendar.watch_id])
    
    watch: Mapped[WatchedCalendar] = relationship(back_populates="summaries")
    
    def __repr__(self):
        return (f"EventSummary(server={self.server_id}, watch={self.watch_id},"
                +f"id={self.summary_id}, msgs={self.message_id})")

