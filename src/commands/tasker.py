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

from typing import Optional
from datetime import timedelta
from functools import wraps

from discord.ext import tasks, pages, commands
from discord.utils import basic_autocomplete as autocomp
from discord import CategoryChannel, Role, Option, Attachment, ApplicationContext
from discord import Member

from .interactions.common import DangerForm
from .interactions.common import access_control
from .common import TimeDelta

from tasker import tasker_core
from tasker.task_text_input import tasks_parser

async def get_projects(ctx):
  return tasker_core.get_guild_projects(str(ctx.interaction.guild.id))

def project_checks(admin=True):
  def dec(f):
    @wraps(f)
    async def new_f(self, ctx: ApplicationContext, *args, **kwargs):
      if 'project' not in kwargs:
        return await ctx.respond(content=f"Erreur interne dans la commande.",
                                 ephemeral=True)
      p = kwargs['project']
      if not tasker_core.check_project_exists(ctx.guild.id, p):
        return await ctx.respond(content=f"Le projet '{p}' nexiste pas.",
                                 ephemeral=True)
      is_allowed = not admin or tasker_core.is_project_admin(
        ctx.user.id,
        ctx.guild.id,
        p
      )
      if not is_allowed:
        return await ctx.respond(
          content=f"Opération non autorisée. {ctx.user.mention} n'est pas "
                 +f"admin dans le projet {p}."
                 + "(/set_project_admin)",
          ephemeral=True)
      return await f(self, ctx, *args, **kwargs)
    return new_f
  return dec   


class TaskerCommands(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    self._last_member = None
  
  @commands.slash_command(description='Create a new Project')
  @access_control(2)
  async def create_project(self, ctx, title, category: CategoryChannel):
    if len(title)>100:
      return await ctx.respond(content=f'Impossible de créer un projet avec ce titre. La taille du titre doit être inférieure à 100.', ephemeral=True)
    await ctx.respond(content=f'Création du projet "{title}"...', ephemeral=True)
    project, forum = await tasker_core.create_project(ctx.guild, title, 
                                                      category, ctx.user.id)
    await ctx.edit(content="Projet créé avec succès, forum: "+forum.mention)
  
  
  @commands.slash_command(description='Set a remainder frequency for a Project')
  @project_checks(admin=True)
  async def set_project_remainder(
    self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    reminder : TimeDelta
  ):
    if reminder == timedelta(seconds=0):
      tasker_core.remove_reminder(str(ctx.guild.id), project)
      await ctx.respond(content='Rappels supprimés pour le projet "{project}"', ephemeral=True) 
    elif type(reminder) is commands.BadArgument:
      await ctx.respond(content=f'Échec de la commande. {reminder} est un mauvais argument. Exemple de bon format : "3 days, 1 hours, 7 minutes"', ephemeral=True)
    else:
      async def act():
        tasker_core.set_reminder(str(ctx.guild.id), project, reminder)
        await ctx.respond(content=f'Fréquence de rappels mise à {reminder} pour le projet "{project}"', ephemeral=True)
      if reminder <= timedelta(hours=1):
        await ctx.respond(content=f"# ATTENTION, DÉLAI DE RAPPEL MIS À SEULEMENT {reminder}. RISQUE DE SPAM.",
                          view=DangerForm(act), ephemeral=True)
      else:
        await act()
  
  
  @commands.slash_command(description='Add a mention/role to a project')
  @project_checks(admin=True)
  async def add_project_role(
    self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    role : Role
  ):
    tasker_core.add_project_role(str(ctx.guild.id), project, role.mention)
    await ctx.respond(f"Role {role.mention} ajouté.", ephemeral=True)
  
  
  @commands.slash_command(description='Remove a mention/role from a project')
  @project_checks(admin=True)
  async def remove_project_role(
    self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    role : Role
  ):
    tasker_core.remove_project_role(str(ctx.guild.id), project, role.mention)
    await ctx.respond(f"Role {role.mention} supprimé.", ephemeral=True)
  
  
  @commands.slash_command(description='Add many tasks to a project from a file')
  @project_checks(admin=True)
  async def bulk_add_tasks(
    self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    file : Attachment
  ):
    if file.size >= 10*1024*1024:
      return await ctx.respond(content=f'Le fichier {file.filename} est trop grand. Taille maximale: 10MB', ephemeral=True)
    try :
      tasks = tasks_parser.parse((await file.read()).decode()) #TODO handle errors
    except Exception:
      return await ctx.respond("Erreur inconnue lors de la lecture du fichier.", ephemeral=True)
    await ctx.defer(ephemeral=True)
    try:
      await tasker_core.bulk_create_tasks(str(ctx.guild.id), project, tasks)
    except tasker_core.TaskAlreadyExists as t:
      return await ctx.respond(f"Erreur. La tâche '{t}' existait déjà", ephemeral=True)
    await ctx.respond("Tâches créées avec succès.", ephemeral=True)
  
  
  @commands.slash_command(description='Make a member an admin for a project')
  @project_checks(admin=False)
  @access_control(2)
  async def set_project_admin(self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    user : Member,
    to : Option(bool, default=True, choices=[True, False])
  ):
    tasker_core.set_project_admin(str(ctx.guild.id), project, user.id, to)
    await ctx.respond("Done.", ephemeral=True)
    
