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
import pytz
import utils

from discord.ext import tasks, pages, commands
from discord.utils import basic_autocomplete as autocomp
from discord import CategoryChannel, Role, Option, Attachment, ApplicationContext
from discord import Member, TextChannel, ForumChannel

from .interactions.common import DangerForm
from .interactions.common import access_control
from .common import TimeDelta, Time

from tasker import tasker_core, tasker_pretty
from tasker.task_text_input import tasks_parser
from database.tasker import *
from sqlalchemy.orm import Session
from database import engine
from bot import bot

async def get_projects(ctx):
  return tasker_core.get_guild_projects(str(ctx.interaction.guild.id))
async def get_project_tasks(ctx):
  proj = ctx.options['project']
  if proj is None: return []
  return tasker_core.get_project_tasks(str(ctx.interaction.guild.id), proj)
async def get_timezones(ctx): #TODO better selector
  return pytz.all_timezones #TODO fix reverted GMT+t

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
      bot_has_permissions = await tasker_core.check_forum_permissions(
        ctx.guild.id,
        p
      )
      if not bot_has_permissions:
        return await ctx.respond(
          content=f"Opération impossible car je n'ai pas les accès "
                 +f"au forum associé au projet {p}."
                 +f"Il me faut les droits pour créer des threads et "
                 +f"pour envoyer des messages dans les threads du forum.",
          ephemeral=True
        )
      return await f(self, ctx, *args, **kwargs)
    return new_f
  return dec

def file_checks(*file_args, max_file_size=10*1024*1024):
  def dec(f):
    @wraps(f)
    async def new_f(self, ctx: ApplicationContext, *args, **kwargs):
      read_files = {}
      for kwarg in file_args: 
        if kwarg not in kwargs:
          await ctx.respond(f"Erreur interne dans la commande.", ephemeral=True)
          return
        if kwargs[kwarg] is not None:
          file = kwargs[kwarg]
          if file.size >= max_file_size:
            return await ctx.respond(
              f'Le fichier {file.filename} est trop grand.'
             +f'Taille maximale: {max_file_size/1024/1024}MB',
              ephemeral=True
            )
          try :
            read_files[kwarg] = (await file.read()).decode() #TODO handle errors
          except Exception:
            return await ctx.respond(
              "Erreur inconnue lors de la lecture du fichier.",
              ephemeral=True
            )
      kwargs.update(read_files)
      return await f(self, ctx, *args, **kwargs)
    return new_f
  return dec


class TaskerCommands(commands.Cog):
  def __init__(self, bot):
    self.bot = bot
    self._last_member = None
  
  @commands.slash_command(description='Set timezone for server')
  @access_control(2)
  async def timezone(self, #TODO this belongs in common
    ctx,
    timezone : Option(str, autocomplete=autocomp(get_timezones))
  ):
    if timezone not in pytz.all_timezones:
      return await ctx.respond(
        "Cette timezone n'est pas valide. Elle doit être parmi les identifants"
       +"présents ici :"
       +"https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
       ephemeral=True
      )
    tasker_core.set_timezone(ctx.guild.id, timezone)
    await ctx.respond(f"Timezone mise à {timezone}", ephemeral=True)
  
  @commands.slash_command(description='Create a new Project')
  @access_control(2)
  async def create_project(self, ctx,
    forum:ForumChannel,
    title: str,
    category: CategoryChannel
  ):
    if len(title)>100:
      return await ctx.respond(content=f'Impossible de créer un projet avec ce titre. La taille du titre doit être inférieure à 100.', ephemeral=True)
    await ctx.respond(content=f'Création du projet "{title}"...', ephemeral=True)
    project, forum = await tasker_core.create_project(ctx.guild, title, forum,
                                                      category, ctx.user.id)
    await ctx.edit(content="Projet créé avec succès, forum: "+forum.mention)
  
  
  @commands.slash_command(description='Set a remainder frequency for a Project')
  @project_checks(admin=True)
  @file_checks('template')
  async def set_project_remainder(
    self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    reminder : TimeDelta,
    template : Option(Attachment, default=None)
  ):
    if reminder == timedelta(seconds=0):
      tasker_core.remove_reminder(str(ctx.guild.id), project)
      await ctx.respond(content=f'Rappels supprimés pour le projet "{project}"', ephemeral=True) 
    elif type(reminder) is commands.BadArgument:
      await ctx.respond(content=f'Échec de la commande. {reminder} est un mauvais argument. Exemple de bon format : "3 days, 1 hours, 7 minutes"', ephemeral=True)
    else:
      async def act():
        tasker_core.set_reminder(str(ctx.guild.id), project, reminder, template)
        await ctx.respond(content=f'Fréquence de rappels mise à {reminder} pour le projet "{project}"', ephemeral=True)
      if reminder <= timedelta(hours=1):
        await ctx.respond(content=f"# ATTENTION, DÉLAI DE RAPPEL MIS À SEULEMENT {reminder}. RISQUE DE SPAM.",
                          view=DangerForm(act), ephemeral=True)
      else:
        await act()

  @commands.slash_command(description='Set reminder template for a project.')
  @project_checks(admin=True)
  @file_checks('template') #TODO typecheck and make test
  async def set_reminder_template(
    self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    template : Option(Attachment, default=None)
  ):
    tasker_core.set_reminder_template(ctx.guild.id, project, template)
    await ctx.respond("Template mis avec succès.", ephemeral=True)
  
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
  @file_checks('file')
  async def bulk_add_tasks(
    self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    file : Attachment
  ):
    from lark import UnexpectedInput #TODO not this
    await ctx.defer(ephemeral=True)
    try :
      tasks = tasks_parser.parse(file) #TODO handle errors
    except UnexpectedInput as e:
      return await ctx.respond(f"Erreur lors de l'analyse des taches:\n{e.get_context(file)}", ephemeral=True)
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
  
  
  @commands.slash_command(description='Make a main thread for a project')
  @project_checks(admin=True)
  @file_checks('main_template', 'secondary_template', max_file_size=1024*1024)
  async def make_project_thread(self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    thread_title : Option(str, max_length=100),
    main_template : Option(Attachment, default=None),
    secondary_template: Option(Attachment, default=None),
    replace : Option(bool, default=False, choices=[True, False])
  ):
    await ctx.defer(ephemeral=True)
    thread = await tasker_core.has_main_thread(ctx.guild.id, project)
    if thread and not replace:
      return await ctx.respond(
       f'Un thread principal ({thread.mention}) existe déjà '
       +f'pour le projet {project}.\nUtilisez /remove_main_thread pour '
       +f'dissocier le thread déjà présent ou mettez l\'option "replace" '
       +f'à True dans cette commande pour modifier le thread déjà présent.',
       ephemeral=True)
    if (main_template is None):
      res = await tasker_core.publish_main_thread(ctx.guild.id, project, thread_title)
      return await ctx.respond(f"Done. {res.mention}")
    if main_template is not None:
      try:
        await tasker_core.validate_template(ctx.guild.id, project, main_template)
      except tasker_core.BadTemplateFormat as e:
        return await ctx.respond(
          f"Erreur dans la lecture du Template du message principal.\n"
         +f"{e.args[0]}",
          ephemeral= True
        )
    if secondary_template is not None:
      try:
        await tasker_core.validate_template(ctx.guild.id, project, sec_template)
      except tasker_core.BadTemplateFormat as e:
        return await ctx.respond(
          f"Erreur dans la lecture du Template du message secondaire.\n"
         +f"{e.args[0]}",
          ephemeral=True
        )
    res = await tasker_core.publish_main_thread(
      ctx.guild.id, project, thread_title,
      main_template, secondary_template
    )
    return await ctx.respond(f'Fait. {res.mention}', ephemeral=True)
  
  @commands.slash_command(description='Remove a thread from a project')
  @project_checks(admin=True)
  async def remove_project_thread(self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    delete : Option(bool, default=False, choices=[False, True])
  ):
    await tasker_core.remove_main_thread(ctx.guild.id, project, delete)
    await ctx.respond("Fait.", ephemeral=True)
  
  @commands.slash_command(description='Make a project alert')
  @project_checks(admin=True)
  @file_checks('template')
  async def make_project_alert(self,
    ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    new_title : Option(str, max_length=200),
    channel : TextChannel,
    kind : Option(
      str, 
      choices=['timely', 'on_create', 'on_complete']
    ),
    frequency : Optional[TimeDelta],
    start : Optional[Time],
    template : Option(Attachment, default=None)
  ):
    if kind == 'timely' and type(frequency) is commands.BadArgument:
      return await ctx.respond(
        "Mauvais format pour la fréquence. "
       +"Exemple de bon format: '7 days, 5 hours, 7 seconds'",
        ephemeral=True
      )
    elif kind == 'timely' and frequency is None:
      return await ctx.respond(
        "Pour une alerte régulière, il faut préciser une fréquence.",
        ephemeral=True
      )
    elif type(start) is commands.BadArgument:
      return await ctx.respond(
        "Mauvais format pour la date. Format: YYYY-MM-DD HH:MM:SS",
        ephemeral=True
      )
    d = {'timely':ProjectAlert.FREQUENT, 'on_create':ProjectAlert.ON_CREATE,
         'on_complete':ProjectAlert.ON_COMPLETE } 
    tasker_core.create_project_alert(
      ctx.guild.id, project, str(channel.id),
      new_title, d[kind], freq=frequency, template=template, start=start
      #TODO check alert id uniqueness
    )
    await ctx.respond("Alerte créée avec succès.", ephemeral=True) 
  
  @commands.slash_command(description='Show main message down here')
  async def show_main_message(self, ctx):
    with Session(engine) as s, s.begin(): 
    #TODO tasker_core.(wrap things with a session and keep it and return it)
      task = tasker_core.find_task_by_thread(ctx.channel_id, s)
      if task:
        msg = tasker_pretty.make_main_task_message(task, s)
        msg['ephemeral'] = True
        await ctx.respond(**msg)
  
  @commands.slash_command(description='Update main thread messages for a project')
  @project_checks(admin=False)
  async def update_thread(self, ctx,
    project : Option(str, autocomplete=autocomp(get_projects))
  ):
    await ctx.defer(ephemeral=True)
    await tasker_core.update_main_thread_of(project, ctx.guild.id)
    await ctx.respond('Fait!')
  
  @commands.slash_command(description='Summary of your tasks in a project')
  @project_checks(admin=False)
  async def personnal_project_summary(self, ctx,
    project : Option(str, autocomplete=autocomp(get_projects))
  ):
    await ctx.defer(ephemeral=True)
    msg = tasker_core.contributor_summary_message(
      ctx.guild.id, project, ctx.user.id
    )
    async def sender(what):
      await ctx.followup.send(what, ephemeral=True)
    await utils.publish_long_ephemeral(sender, msg)
  
  @commands.slash_command(description='See statistics on contributor roles')
  @project_checks(admin=True)
  async def project_contributors_stats(self, ctx,
    project : Option(str, autocomplete=autocomp(get_projects))
  ):
    await ctx.defer(ephemeral=True)
    msg = tasker_core.project_contributors_stats(
      ctx.guild.id, project
    )
    async def sender(what):
      await ctx.followup.send(what, ephemeral=True)
    await utils.publish_long_ephemeral(sender, msg)

  @commands.slash_command(description='Create a new task in a project')
  @project_checks(admin=True)
  async def create_new_task(self, ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    task_title : str,
    task_description : Option(str, default=None),
    start_date : Option(Time, default=None),
    end_date : Option(Time, default=None),
  ):
    await ctx.defer(ephemeral=True)
    BadArgument = commands.BadArgument
    if type(start_date) is BadArgument or type(end_date) is BadArgument:
      #TODO: unified argument checking in cmds
      return await ctx.respond(
        'Mauvais format de date. '+
        'Bon format: "YYYY-MM-DD" ou "YYYY-MM-DD HH:MM:SS"'
      )
    try:
      new_task = Task(
        title=task_title,
        description=task_description,
        starts_after=start_date.isoformat() if start_date else None,#TODO: ...
        ends_before=end_date.isoformat() if end_date else None
      )
      thread = await tasker_core.create_task(ctx.guild.id, project, new_task)
      await ctx.respond(f'Done! {thread.mention}')
    except tasker_core.TaskAlreadyExists as e:
      await ctx.respond(f'Une tâche nommée "{e.args[0]}" existe déjà.')
  
  @commands.slash_command(description='Create a new task in a project')
  @project_checks(admin=True)
  async def delete_project_task(self, ctx,
    project : Option(str, autocomplete=autocomp(get_projects)),
    task : Option(str, autocomplete=autocomp(get_project_tasks)),
    delete_thread : Option(bool, choices=[False, True])
  ):
    await ctx.defer(ephemeral=True)
    try:
      await tasker_core.delete_task(ctx.guild.id, project, task, delete_thread)
    except tasker_core.TaskDoesNotExist:
      await ctx.respond(f'La tâche "{task}" n\'existe pas :(')
    else:
      await ctx.respond(f'Tâche "{task}" supprimée avec succès')
  
  @commands.slash_command(description='Update all task threads at once')
  @project_checks(admin=True)
  async def update_all_task_messages(self, ctx,
    project : Option(str, autocomplete=autocomp(get_projects))
  ):
    await ctx.defer(ephemeral=True)
    await tasker_core.update_all_tasks_messages(ctx.guild.id, project)
    await ctx.respond(f'Fait!')
  
  @commands.slash_command(
    description='Delete a message from the bot. '
                'Needs to be executed in the message\'s channel'
  )
  @access_control(2)
  async def delete_bot_message(self, ctx, message_id):
    await ctx.defer(ephemeral=True)
    if (m:=await utils.fetch_message_opt(ctx.channel_id, message_id)) is None:
      return await ctx.respond('Je n\'ai pas pu trouver le message')
    if (m.author != bot.user):
      return await ctx.respond(f'Ce message n\'a pas été écrit par moi...')
    await utils.purge_opt_message_list([m])
    await ctx.respond('Fait.')
