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

from discord.ui import View, button
from discord import ButtonStyle
import discord
from sqlalchemy.orm import Session
import asyncio
from datetime import datetime
from typing import Optional

from tasker import tasker_core, tasker_graph
from database import engine
from database.tools import get_or_create
from database.tasker import *
from .common import DangerForm, ActionModal
from .common import paginated_selector

lock = asyncio.Lock()
#TODO: add decorators to views integrating a lock and task existence check

async def find_task_or_tell(interaction, s=None) -> Optional[Task] :
  if s is None:
    with Session(engine) as s, s.begin():
      return await find_task_or_tell(interaction, s)
  task = tasker_core.find_task_by_thread(str(interaction.channel_id), s=s)
  if task is not None:
    return task
  msg = {
    'content' : f"Aucune tâche n'est associée à ce thread :(",
    'ephemeral' : True
  }
  if interaction.response.is_done():
    await interaction.followup.send(**msg)
  else:
    await interaction.response.send_message(**msg)
  return None

class TaskInteractView(View): #TODO SANITIZE ALL USER INPUT
  def __init__(self):
    super().__init__(timeout=None)
  
  async def common_choice_declaration(self, interaction, Kind):
    await interaction.response.defer(ephemeral=True)
    async with lock:
     with Session(engine) as s, s.begin():
       user_id, channel_id = interaction.user.id, interaction.channel_id
       if (task := await find_task_or_tell(interaction, s)) is None:
         return
       task_id = (task.project_id, task.title)
       task_title = task.title
       contrib=tasker_core.is_task_contributor(Kind, str(user_id), task, s=s)
     if contrib:
       async def act():
        async with lock:
          with Session(engine) as s, s.begin():
           if (task := await find_task_or_tell(interaction, s)) is None:
            return
           await tasker_core.remove_task_contributor(Kind, task, str(user_id),s)
       what = {TaskParticipant:"participant.e", TaskInterested:"interessé.e",
               TaskVeteran:"pouvant aider", TaskMoteur:"moteur.rice"}
       return await interaction.followup.send(
         content=(f'{interaction.user.mention}, confirmes-tu vouloir ne plus être '
                 +f'considéré.e comme {what[Kind]} pour la tâche "{task_title}" ?'),
         view=DangerForm(act, double_check=False),
         ephemeral=True
       )
     with Session(engine) as s, s.begin():
      if (task := await find_task_or_tell(interaction, s)) is None:
        return
      await tasker_core.add_task_contributor(Kind, task, str(user_id), s=s)
     await interaction.followup.send("Done!", ephemeral=True) #TODO better message
  
  #TODO emojis :-)
  @button(label='Je participe!', custom_id='choose_task_button', style=ButtonStyle.primary, row=0)
  async def active_callback(self, button, interaction):
    await self.common_choice_declaration(interaction, TaskParticipant)
  @button(label='Intéressé.e!', custom_id='intersted_task_button', style=ButtonStyle.primary, row=0)
  async def interested_callback(self, button, interaction):
    await self.common_choice_declaration(interaction, TaskInterested)
  @button(label='Veux plus d\'infos', custom_id='veteran_task_button', style=ButtonStyle.primary, row=0)
  async def veteran_callback(self, button, interaction):
    await self.common_choice_declaration(interaction, TaskVeteran)
  @button(label='Je deviens moteur.rice', custom_id='moteur_task_button', style=ButtonStyle.primary, row=0)
  async def moteur_callback(self, button, interaction):
    await self.common_choice_declaration(interaction, TaskMoteur)
  
  @button(
    label='Écrire dans le Journal de Bord',
    custom_id='log_button',
    style=ButtonStyle.gray,
    row=1
  )
  async def log_callback(self, button, interaction):
      s = Session(engine)
      thread, user = str(interaction.channel_id), str(interaction.user.id)
      if (task := await find_task_or_tell(interaction, s)) is None:
        return
      who = get_or_create(
       s, Contributor,
       member_id=user, project_id=task.project_id
      )
      if (
        task in who.current_tasks
        or who.project_admin
      ):
        async def cback(self2, interaction2):
          message = self2.children[0].value
          if await find_task_or_tell(interaction2) is None:
            return
          await tasker_core.task_user_log(task, who, message, s=s)
          s.commit()
          s.close()
          await interaction2.response.send_message(f'Bravo :]', ephemeral=True)
        modal = ActionModal(
          "Entrez votre message dans le journal.",
           cback, "LOG", try_mentions=True
        )
        await interaction.response.send_modal(modal)
      else:
        await interaction.response.send_message(
          "Seule une personne qui participe à la tâche/un.e admin"
          +" peut écrire dans le journal",
          ephemeral=True
        )
  @button(
    label='Modifier entrée Journal',
    custom_id='edit_log_button',
    style=ButtonStyle.gray,
    row=1
  )
  async def edit_log_callback(self, button, interaction):
    if await find_task_or_tell(interaction) is None: return
    await interaction.response.send_message(
      f'<@{interaction.user.id}>, choisissez une entrée à modifier',
      view=EditLogView(interaction.channel_id, interaction.user.id),
      ephemeral=True
    )
  
  @button(
    label='Pourcentage d\'avancement',
    custom_id='percentage_button',
    style=ButtonStyle.green,
    row=1
  )
  async def percentage_callback(self, button, interaction):
    if await find_task_or_tell(interaction) is None: return
    async def cback(self2, interaction2):
     with Session(engine) as s, s.begin():
      try:
        await interaction2.response.defer(ephemeral=True)
        thread = str(interaction.channel_id)
        if (task := await find_task_or_tell(interaction, s)) is None:
          return
        new = self2.children[0].value
        new = int(new)
        if new < 0 or new > 100:
          await interaction2.followup.send(
            "Le poucentage d'avancement doit être entre 0 et 100",
            ephemeral=True
          )
        else:
          if await find_task_or_tell(interaction) is None: return
          await tasker_core.update_advancement(task, new, s)
          await interaction2.followup.send(
            "Avencement mis à jour avec succès.", ephemeral=True
          )
      except ValueError:
        await interaction2.followup.send(
          "Erreur. L'avancement doit être un entier entre 0 et 100",
          ephemeral=True
        )
    modal = ActionModal("Entre le nouveau poucentage pour la tâche", cback, "0-100")
    await interaction.response.send_modal(modal)
  @button(
    label='Modifier les étapes',
    custom_id='edit_steps_button',
    style=ButtonStyle.red,
    row=3
  )
  async def edit_steps_callback(self, button, interaction):
    if await find_task_or_tell(interaction) is None: return
    await interaction.response.send_message(
      "Choisissez une tâche à modificer!",
      ephemeral=True, 
      view=EditStepView(interaction.channel_id, TaskStep.SUBTASK)
    )
  @button(
    label='Modifier les remarques',
    custom_id='edit_ps_button',
    style=ButtonStyle.red,
    row=3
  )
  async def edit_ps_callback(self, button, interaction):
    if await find_task_or_tell(interaction) is None: return
    await interaction.response.send_message(
      "Choisissez une remarque à modifier!",
      ephemeral=True,
      view=EditStepView(interaction.channel_id, TaskStep.REMARK)
    )
  @button(
    label='Nouvelle étape/remarque',
    custom_id='add_step_button',
    style=ButtonStyle.green,
    row=3
  )
  async def add_step_callback(self, button, interaction):
    if await find_task_or_tell(interaction) is None: return
    await interaction.response.send_message(
      'C:', ephemeral=True,
      view=AddStepView()
    )
  
  @button(
    label='Ajouter/Retirer dépendance',
    row=4,
    custom_id='add_dependency_button',
  )
  async def add_dep_callback(self, button, interaction):
    if await find_task_or_tell(interaction) is None: return
    await interaction.response.send_message(
      'C:', ephemeral=True,
      view=AddDependencyView(interaction.channel_id)
    )
  
  @button(
    label='Mettre à jour message',
    row=4,
    custom_id='updmsg'
  )
  async def upd_callback(self, button, interaction):
    await interaction.response.defer(ephemeral=True)
    if await find_task_or_tell(interaction) is None: return
    await tasker_core.update_task_of(interaction.channel_id)
    await interaction.followup.send(content='Done!', ephemeral=True)

def EditStepView(thread_id, what):
  with Session(engine) as s:
    task = tasker_core.find_task_by_thread(str(thread_id), s)
    
    # Task existence is checked just before calling this but since there is no
    # concurrency handling for now it is technically possible to produce a
    # situation where task is None here.
    # With this handling, there will be a message to choose a step but no view
    # to go with it. When trying again to get the view, a message indicating
    # that not task is present.
    # TLDR: TODO remove this check when concurrency is correctly handled
    if task is None: return None
    
    options = [
      (
        s.step_id,
        f'{s.step_number if s.step_number else "PS"}-{s.step_description}'
      )
      for s in task.steps
      if what == s.kind
    ]
    descriptions = {s.step_id: s.step_description for s in task.steps}
    is_step = {s.step_id: (s.kind == TaskStep.SUBTASK) for s in task.steps}
  
  
  class EditStepView(View):
     def __init__(self):
       super().__init__()
       self.step = -1
     
     @paginated_selector(
       name = "Laquelle modifier?",
       row = 0,
       options = options,
       to_str = lambda x: x[1]
     )
     async def task_choose_callback(self, select, interaction, value):
       select.placeholder = value[1][:149]
       self.step = value[0]
       await interaction.response.edit_message(view=self)
     
     @button(
       label = f'Supprimer',
       row = 1,
       style=discord.ButtonStyle.red
     )
     async def del_callback(self, button, interaction):
       if self.step == -1:
         return await interaction.response.send_message(
           "Il faut d'abord en choisir une!",
           ephemeral=True
         )
       await interaction.response.defer()
       if await find_task_or_tell(interaction) is None: return
       await tasker_core.delete_step(self.step)
       await interaction.edit_original_response(view=None, content='Fait!')
     
     if what == TaskStep.SUBTASK:
       @button(
         label = f'Changer numéro',
         row = 1,
         style=discord.ButtonStyle.green
       )
       async def num_callback(self, button, interaction):
         if self.step == -1:
           return await interaction.response.send_message(
             "Il faut d'abord choisir une étape!",
             ephemeral=True
           )
         if await find_task_or_tell(interaction) is None: return
         async def cback(self2, interaction2):
           a = self2.children[0].value
           try:
             a = float(a)
             if await find_task_or_tell(interaction) is None: return
             await tasker_core.edit_step_number(self.step, a)
             await self.message.edit(view=None, content='Done!')
             await interaction2.response.defer()
           except ValueError:
             return await interaction2.response.send_message(
                f'Erreur! Il faut mettre un nombre (0, -7, 8.45, etc...)',
                ephemeral=True
             )
         modal = ActionModal('Entrez un numéro d\'étape', cback, "2, 3.8, etc")
         await interaction.response.send_modal(modal)
       
       @button(
         label = f'Cocher/décocher',
         row = 1,
         style=discord.ButtonStyle.green
       )
       async def check_callback(self, button, interaction):
         if self.step == -1:
           return await interaction.response.send_message(
             "Il faut d'abord choisir une étape!",
             ephemeral=True
           )
         await interaction.response.defer()
         if await find_task_or_tell(interaction) is None: return
         await tasker_core.check_step(self.step)
         await interaction.edit_original_response(
           content='Done!', view=None
         )
     
  return EditStepView()

def EditLogView(thread_id, user_id):
  with Session(engine) as s:
    task = tasker_core.find_task_by_thread(str(thread_id), s)
    if task is None: return None #TODO: remove this when concurrency is handled
    d = datetime.fromisoformat
    options = [
      ((l.project_id, l.task_title, l.timestamp, l.member_id),
       f'{d(l.timestamp).date().isoformat()}: {l.log_message}'
      )
      for l in task.logs[::-1]
      if l.log_type == TaskLog.USER_LOG and l.member_id == str(user_id)
    ]
    msgs = { (l.project_id, l.task_title, l.timestamp, l.member_id)
             : l.log_message for l in task.logs }
    
  
  class EditLogView(View):
    def __init__(self):
      super().__init__()
      self.log = -1
  
    @paginated_selector(
      name = "Choisir une entrée",
      row = 0,
      options = options,
      to_str = lambda x: x[1]
    )
    async def log_choose_cαllback(self, select, interaction, value):
      select.placeholder = value[1][:149]
      self.log = value[0]
      await interaction.response.send_message(
        content=msgs[value[0]],
        ephemeral=True
      )
    
    @button(
      label = 'Modifier',
      row = 1,
      style=discord.ButtonStyle.red
    )
    async def edit_callback(self, button, interaction):
      if self.log == -1:
         return await interaction.response.send_message(
           "Il faut d'abord en choisir une!",
           ephemeral=True
         )
      async def cback(self2, interaction2):
        await interaction2.response.defer()
        async with lock:
          if await find_task_or_tell(interaction) is None: return
          await tasker_core.edit_log_message(self.log, self2.children[0].value)
        await interaction.edit_original_response(content="Done!", view=None)
      m = ActionModal('Entrez la nouvelle version de l\'entrée', cback, '.')
      await interaction.response.send_modal(m)
    
    @button(
      label = 'Supprimer',
      row = 1,
      style=discord.ButtonStyle.red
    )
    async def delete_callback(self, button, interaction):
      if self.log == -1:
         return await interaction.response.send_message(
           "Il faut d'abord en choisir une!",
           ephemeral=True
         )
      async with lock:
        await interaction.response.defer()
        if await find_task_or_tell(interaction) is None: return
        await tasker_core.delete_log_message(self.log)
        await interaction.edit_original_response(
          view=None, content='Fait!'
        )
  
  return EditLogView()


class AddStepView(View):
  def __init__(self):
    super().__init__()
    self.desc = None
    self.step = None
    self.show = (
      "**Message:** {}\n**Étape:** {}\n"
     +"Pour créer une remarque, ne précisez pas d'étape."
    )
  
  @button(label='Mettre description de tâche/remarque')
  async def desc_callback(self, button, interaction):
    async def cback(self2, interaction2):
      self.desc = self2.children[0].value
      await interaction2.response.defer()
      await interaction.edit_original_response(
        content=self.show.format(self.desc or "Rien", self.step or "Rien"),
        view=self
      )
    m = ActionModal('Entrez la description', cback, 'C:')
    await interaction.response.send_modal(m)
  
  @button(label='Mettre un numéro d\'étape')
  async def step_callback(self, button, interaction):
    async def cback(self2, interaction2):
     a = self2.children[0].value
     try:
       a = float(a)
       self.step = a
       await interaction2.response.defer()
       await interaction.edit_original_response(
        content=self.show.format(self.desc or "Rien", self.step or "Rien"),
        view=self
      )
     except ValueError:
       return await interaction2.response.send_message(
          f'Erreur! Il faut mettre un nombre (0, -7, 8.45, etc...)',
          ephemeral=True
       )
    modal = ActionModal('Entrez un numéro d\'étape', cback, "2, 3.8, etc")
    await interaction.response.send_modal(modal)
  
  @button(label='Valider', style=ButtonStyle.green)
  async def end_callback(self, button, interaction):
    if self.desc is None:
      return await interaction.response.send_message(
        "Il faut d'abord mettre un message!",
        ephemeral=True
      )
    kind = TaskStep.REMARK if self.step is None else TaskStep.SUBTASK
    if await find_task_or_tell(interaction) is None: return
    #TODO: handle concurrency, the check above is not sufficient
    await tasker_core.add_step(
      interaction.channel_id,
      self.desc,
      self.step,
      kind
    )
    await interaction.response.edit_message(
      content="Fait!",
      view=None
    )

def AddDependencyView(channel_id):
  with Session(engine) as s:
    _task = tasker_core.find_task_by_thread(channel_id, s)
    if _task is None: return #TODO: remove this when concurrency is handled
    choices = sorted([
      (task.thread_id, task.title) for task in _task.project.tasks
      if task not in tasker_graph.all_codependencies(_task, s)
    ], key=lambda x:x[1])
  class AddDependencyView(View):
     def __init__(self):
       super().__init__()
       self.chosen_task = None
    
     @paginated_selector(
       name = "Quelle tâche ?",
       row = 0,
       options = choices,
       to_str = lambda x: x[1]
     )
     async def task_choose_callback(self, select, interaction, value):
       select.placeholder = value[1]
       self.chosen_task = value[0]
       await interaction.response.edit_message(view=self)
     
     @button(label='Valider')
     async def end_callback(self, button, interaction):
      if self.chosen_task is None:
        return await interaction.response.send_message(
          "Il faut d'abord choisir une tâche!",
          ephemeral=True
        )
      if await find_task_or_tell(interaction) is None: return
      await tasker_core.add_dependency(channel_id, self.chosen_task)
      await interaction.response.send_message(
        "Ça devrait être bon!",
        ephemeral=True
      )
  return AddDependencyView()
