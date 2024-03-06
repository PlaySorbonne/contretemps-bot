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
from database.tasker import TaskParticipant, TaskInterested, TaskVeteran
from .common import DangerForm


class ChooseTaskView(View): #TODO SANITIZE ALL USER INPUT
  def __init__(self):
    super().__init__(timeout=None)
  
  async def common_choice_declaration(self, interaction, Kind):
    with Session(engine) as s, s.begin():
     user_id, channel_id = interaction.user.id, interaction.channel_id
     task = tasker_core.find_task_by_thread(str(channel_id), s=s)
     if tasker_core.is_task_contributor(Kind, str(user_id), task, s=s):
       async def act():
        await tasker_core.remove_task_contributor(Kind, task, str(user_id))
       what = {TaskParticipant:"participant.e", TaskInterested:"interessé.e",
               TaskVeteran:"pouvant aider"}
       return await interaction.response.send_message(
         content=(f'{interaction.user.mention}, confirmes-tu vouloir ne plus être '
                 +f'considéré.e comme {what[Kind]} pour la tâche "{task.title}" ?'),
         view=DangerForm(act),
         ephemeral=True
       )
     await tasker_core.add_task_contributor(Kind, task, str(user_id),s=s)
    await interaction.response.send_message("Done!", ephemeral=True) #TODO better message
  
  #TODO emojis :-)
  @button(label='Je prends!', custom_id='choose_task_button', style=ButtonStyle.primary)
  async def active_callback(self, button, interaction):
    await self.common_choice_declaration(interaction, TaskParticipant)
  @button(label='Intéressé.e!', custom_id='intersted_task_button', style=ButtonStyle.primary)
  async def interested_callback(self, button, interaction):
    await self.common_choice_declaration(interaction, TaskInterested)
  @button(label='M\'y connais', custom_id='veteran_task_button', style=ButtonStyle.primary)
  async def veteran_callback(self, button, interaction):
    await self.common_choice_declaration(interaction, TaskVeteran)


