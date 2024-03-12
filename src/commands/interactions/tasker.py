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
from sqlalchemy.orm import Session

from tasker import tasker_core
from database import engine
from database.tools import get_or_create
from database.tasker import *
from .common import DangerForm, ActionModal


class TaskInteractView(View): #TODO SANITIZE ALL USER INPUT
  def __init__(self):
    super().__init__(timeout=None)
  
  async def common_choice_declaration(self, interaction, Kind):
    await interaction.response.defer(ephemeral=True)
    with Session(engine) as s, s.begin():
     user_id, channel_id = interaction.user.id, interaction.channel_id
     task = tasker_core.find_task_by_thread(str(channel_id), s=s)
     if tasker_core.is_task_contributor(Kind, str(user_id), task, s=s):
       async def act():
        await tasker_core.remove_task_contributor(Kind, task, str(user_id))
       what = {TaskParticipant:"participant.e", TaskInterested:"interessé.e",
               TaskVeteran:"pouvant aider"}
       return await interaction.followup.send(
         content=(f'{interaction.user.mention}, confirmes-tu vouloir ne plus être '
                 +f'considéré.e comme {what[Kind]} pour la tâche "{task.title}" ?'),
         view=DangerForm(act, double_check=False),
         ephemeral=True
       )
     await tasker_core.add_task_contributor(Kind, task, str(user_id),s=s)
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
  
  @button(
    label='Écrire dans le Journal de Bord',
    custom_id='log_button',
    style=ButtonStyle.gray,
    row=1
  )
  async def log_callback(self, button, interaction):
      s = Session(engine)
      thread, user = str(interaction.channel_id), str(interaction.user.id)
      task = tasker_core.find_task_by_thread(thread, s)
      who = get_or_create(
       s, Contributor,
       member_id=user, project_id=task.project_id
      )
      if (
        task in who.current_tasks or task in who.interesting_tasks
        or who.project_admin
      ):
        async def cback(self2, interaction2):
          message = self2.children[0].value
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
          "Seule un.e admin/une personne qui participe ou aide à la tâche"
          " peut écrire dans le journal",
          ephemeral=True
        )
  @button(
    label='Pourcentage d\'avancement',
    custom_id='percentage_button',
    style=ButtonStyle.green,
    row=1
  )
  async def percentage_callback(self, button, interaction):
    async def cback(self2, interaction2):
     with Session(engine) as s, s.begin():
      try:
        thread = str(interaction.channel_id)
        task = tasker_core.find_task_by_thread(thread, s)
        new = self2.children[0].value
        new = int(new)
        if new < 0 or new > 100:
          await interaction2.response.send_message(
            "Le poucentage d'avancement doit être entre 0 et 100",
            ephemeral=True
          )
        else:
          await tasker_core.update_advancement(task, new, s)
          await interaction2.response.send_message(
            "Avencement mis à jour avec succès.",
            ephemeral=True
          )
      except ValueError:
        await interaction2.response.send_message(
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
    await interaction.response.send_message(
      "Ce bouton n'est pas encore implémenté :(",
      ephemeral=True
    )
