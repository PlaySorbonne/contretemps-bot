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

from discord.ext import tasks, pages, commands
from discord.utils import basic_autocomplete as autocomp
from discord import CategoryChannel, Role, Option, Attachment

from .interactions.common import DangerForm
from .interactions.common import access_control
from .common import TimeDelta

from tasker import tasker_core
from tasker.task_text_input import tasks_parser

async def get_projects(ctx):
  return tasker_core.get_guild_projects(str(ctx.interaction.guild.id))

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
    project, forum = await tasker_core.create_project(ctx.guild, title, category)
    await ctx.edit(content="Projet créé avec succès, forum: "+forum.mention)
  
  @commands.slash_command(description='Set a remainder frequency for a Project')
  @access_control(2)
  async def set_project_remainder(
    self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    reminder : TimeDelta
  ):
    if not tasker_core.check_project_exists(str(ctx.guild.id), project):
      return await ctx.respond(content=f'Le projet "{projet}" n\'existe pas.', ephemeral=True)
    if reminder == timedelta(seconds=0):
      tasker_core.remove_reminder(str(ctx.guild.id), project)
      ctx.respond(content='Rappels supprimés pour le projet "{project}"', ephemeral=True) 
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
  @access_control(2)
  async def add_project_role(
    self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    role : Role
  ):
    if not tasker_core.check_project_exists(str(ctx.guild.id), project):
      return await ctx.respond(content=f'Le projet "{projet}" n\'existe pas.', ephemeral=True)
    tasker_core.add_project_role(str(ctx.guild.id), project, role.mention)
    await ctx.respond(f"Role {role.mention} ajouté.", ephemeral=True)

  @commands.slash_command(description='Remove a mention/role from a project')
  @access_control(2)
  async def remove_project_role(
    self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    role : Role
  ):
    if not tasker_core.check_project_exists(str(ctx.guild.id), project):
      return await ctx.respond(content=f'Le projet "{projet}" n\'existe pas.', ephemeral=True)
    tasker_core.remove_project_role(str(ctx.guild.id), project, role.mention)
    await ctx.respond(f"Role {role.mention} supprimé.", ephemeral=True)
  
  @commands.slash_command(description='Add many tasks to a project from a file')
  @access_control(2)
  async def bulk_add_tasks(
    self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    file : Attachment
  ):
    if not tasker_core.check_project_exists(str(ctx.guild.id), project):
      return await ctx.respond(content=f'Le projet "{projet}" n\'existe pas.', ephemeral=True)
    if file.size >= 10*1024*1024:
      return await ctx.respond(content=f'Le fichier {file.filename} est trop grand. Taille maximale: 10MB', ephemeral=True)
    tasks = tasks_parser.parse((await file.read()).decode()) #TODO handle errors
    await ctx.defer(ephemeral=True)
    await tasker_core.bulk_create_tasks(str(ctx.guild.id), project, tasks)
    await ctx.respond("Tâches créées avec succès.")
    
