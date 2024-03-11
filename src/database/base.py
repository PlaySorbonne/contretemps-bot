from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import mapped_column as mc, Mapped, relationship
from typing import Optional as NULL, List

class Base(DeclarativeBase):
    pass

class ServerConnexion(Base):
    __tablename__ = "server_connexion"
    
    server_id: Mapped[str] = mc(primary_key=True)
    gtoken: Mapped[NULL[str]]
    gmail: Mapped[NULL[str]]
    timezone : Mapped[str] = mc(default='UTC')
    
    access_rules: Mapped[List['UserAccess']] = relationship(back_populates="server")
    watches: Mapped[List['WatchedCalendar']] = relationship(back_populates="server")
    projects: Mapped[List['Project']] = relationship(back_populates="server")
