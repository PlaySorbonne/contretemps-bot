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


import discord

from discord.ext import tasks, pages

from event_notifier import EventNotifier
from google_calendar import GoogleAuthentifier
from bot import server_notifiers, bot

import datetime
import dateutil
import functools


from .common import ActionModal, paginated_selector, DangerForm

################################ VIEWS ################################
class ConnectModal(discord.ui.Modal):
    def __init__(self, gid, x, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.__x = x
        self.gid = gid
        
        self.add_item(discord.ui.InputText(label="Enter the authentification code: ", style=discord.InputTextStyle.long))
    
    async def callback(self, interaction):
        creds = self.__x.get_credentials(self.children[0].value)
        if creds is None :
            await interaction.response.send_message("The given code is bad.", ephemeral=True)
            return
        success, info = server_notifiers[self.gid].connect(creds)
        if success: 
            await interaction.response.send_message(f"Connected succesfully as {info}", ephemeral=True)
        else:
            await interaction.response.send_message(f'Connection failed : {info}', ephemeral=True)

def ConnectView(guildid, x):
    class ConnectView(discord.ui.View):
        @discord.ui.button(label="I got the code", style=discord.ButtonStyle.primary)
        async def button_callback(self, button, interaction):
            modal = ConnectModal(guildid,x, title="Authentification code")
            await interaction.response.send_modal(modal)
    return ConnectView()


def AddWatchForm(guild, cals):
    gid = guild.id

    class AddWatchForm(discord.ui.View):
        
        def __init__(self):
            super().__init__()
            self.channel = None
            self.cal = None
            self.upd_new = True
            self.upd_del = True
            self.upd_mod = True
            self.cal_page = 0
            
        
        @paginated_selector(
            name = "calendar",
            row = 0,
            options = cals,
            to_str = lambda c : c['name']
        )
        async def select_callback_1(self, select, interaction, choice):
            select.placeholder = choice['name']
            self.cal = choice
            await interaction.response.edit_message(view=self)
                
        @discord.ui.select(
            placeholder = "Choose a channel",
            select_type=discord.ComponentType.channel_select,
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread
            ],
            min_values=1,
            max_values=1,
            row=1
        )
        async def select_callback_2(self, select, interaction):
            self.channel = str(select.values[0].id)
            await interaction.response.edit_message(view=self)
        
        @discord.ui.button(label="NewEvents", style=discord.ButtonStyle.success, row=2)
        async def select_callback_3(self, button, interactions):
            if self.upd_new == 1:
                button.style = discord.ButtonStyle.danger
                self.upd_new = 0
            else:
                button.style = discord.ButtonStyle.success
                self.upd_new = 1
            await interactions.response.edit_message(view=self)
        @discord.ui.button(label="DeletedEvents", style=discord.ButtonStyle.success, row=2)
        async def select_callback_4(self, button, interactions):
            if self.upd_del == 1:
                button.style = discord.ButtonStyle.danger
                self.upd_del = 0
            else:
                button.style = discord.ButtonStyle.success
                self.upd_del = 1
            await interactions.response.edit_message(view=self)
        @discord.ui.button(label="ModifiedEvents", style=discord.ButtonStyle.success, row=2)
        async def select_callback_5(self, button, interactions):
            if self.upd_mod == 1:
                button.style = discord.ButtonStyle.danger
                self.upd_mod = 0
            else:
                button.style = discord.ButtonStyle.success
                self.upd_mod = 1
            await interactions.response.edit_message(view=self)
            
        @discord.ui.button(label="Confirm", style=discord.ButtonStyle.primary, row=3)
        async def select_callback_6(self, button, interactions):
            if self.channel is not None and self.cal is not None:
                async def cback(self2, interaction2):
                    hey = self2.children[0].value
                    if not server_notifiers[gid].check_watch_uniqueness(hey):
                        await self.message.edit('An event notifier with that name already exists...')
                        await interaction2.response.defer()
                    else : 
                        await server_notifiers[gid].add_watch(self.channel, self.cal, self.upd_new, self.upd_mod, self.upd_del,hey) 
                        await self.message.delete()
                        await interaction2.response.send_message(f'Succesfully added notifier', ephemeral=True)
                modal = ActionModal("Please enter a notifier name which is unique", cback, "Name")
                await interactions.response.send_modal(modal)
            else:
                await interactions.response.send_message(f'You need to select a calendar and a channel before confirming.', ephemeral=True)
            
           
    return AddWatchForm()


#TODO: option for extended summary form (showing location/description of events ?)
def MakeSummaryForm(guild): #TODO handle if there is no watch (0 elements to select from in the list)
    gid = guild.id
    cals = server_notifiers[gid].get_all_watched_cals()
    formated = []
    for c in cals:
        cname = bot.get_channel(int(c['channel_id'])).name
        calname = c['watch_id']
        formated.append((c,f'Channel: #{cname} ----- {calname}'))
    today = datetime.date.today()
    now = datetime.datetime.now()
    min_date = now - datetime.timedelta(days=30)
    max_date = now + datetime.timedelta(days=365)
    date_message = f'Date must be after {min_date.isoformat()} and before {max_date.isoformat()}'
        
        
    class MakeSummaryForm(discord.ui.View):
        
        def __init__(self):
            super().__init__()
            self.watched_cal = None
            self.duration = 7
            self.in_months = 0
            self.base_day = today
            self.header = ""
            
        
        @paginated_selector(
            name = "Event Notifier",
            row = 0,
            options = formated,
            to_str = lambda x : x[1]
        )
        async def select_callback_1(self, select, interaction, value):
            select.placeholder = value[1]
            self.watched_cal = value[0]
            await interaction.response.edit_message(view=self)
        
        @discord.ui.button(label = f"Starting on day: {today}", style=discord.ButtonStyle.primary, row=1)
        async def select_callback_2(self, button, interaction):
            async def cback(self2, interaction2):
                when = self2.children[0].value
                try:
                    bd = datetime.datetime.fromisoformat(when)
                    if bd < min_date or bd > max_date:
                        await interaction2.response.send_message(
                            f'{when} is not a valid date. {date_message}',
                            ephemeral = True
                        )
                        return
                    self.base_day = bd
                    button.label = f"Starting on day: {self.base_day.isoformat()}"
                    await self.message.edit(self.message.content, view=self)
                    await interaction2.response.defer()
                except ValueError:
                    await interaction2.response.send_message(f'"{when}" is an invalid date format.', ephemeral=True)
            modal = ActionModal(f"Starting day in format YYYY-MM-DD HH:MM.", cback, "Start summary time")
            await interaction.response.send_modal(modal)
        
        @discord.ui.button(label="Reset every 7...", style=discord.ButtonStyle.primary, row=2, custom_id='reset')
        async def select_callback_10(self, button, interaction):
            async def cback(self2, interaction2):
                a = self2.children[0].value
                try:
                    n = int(a)
                    if n <= 0 or (self.in_months and n>12) or n>365:
                        raise ValueError("Frequency must be strictly positive")
                    self.duration = n
                    button.label = f'Reset every {n}...'
                    await self.message.edit(self.message.content, view=self)
                    await interaction2.response.defer()
                except ValueError:
                    await interaction2.response.send_message(f'Bad value for frequency: "{a}"', ephemeral=True)
            modal = ActionModal("Frequency : (>0 and <=365d/12m)", cback, "Update Frequency")
            await interaction.response.send_modal(modal)  
        
        @discord.ui.button(label="days", style=discord.ButtonStyle.primary, row=2)
        async def select_callback_3(self, button, interactions):
            if self.in_months == 0:
                button.label="months"
                self.in_months = 1
                self.duration = 1
                self.get_item('reset').label='Reset every 1...'
            else:
                button.label="days"
                self.in_months = 0
                self.duration = 7
                self.get_item('reset').label='Reset every 7...'
            await interactions.response.edit_message(view=self)

        @discord.ui.button(label="Set Header", style=discord.ButtonStyle.primary, row=3)
        async def header_button_callback(self, button, interaction):
            async def cback(self2, interaction2):
                self.header = self2.children[0].value
                await self.message.edit(f'Header:\n{self.header}', view=self)
                await interaction2.response.defer()
            modal = ActionModal("Write the header message", cback, "Header message")
            await interaction.response.send_modal(modal)
        
        @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, row=4)
        async def select_callback_6(self, button, interactions):
            if self.watched_cal is not None:
                async def cback(self2, interaction):
                    hey = self2.children[0].value
                    if not server_notifiers[gid].check_summary_uniqueness(self.watched_cal['watch_id'],hey): 
                        await self.message.edit('A summary with that name already exists...')
                        await interaction.response.defer()
                    else : 
                        await server_notifiers[gid].add_summary(self.watched_cal, self.duration, self.in_months, self.base_day,self.header, hey) 
                        await self.message.delete()
                        await interaction.response.send_message(f'Succesfully added summary', ephemeral=True)
                modal = ActionModal("Please enter a summary title which is unique", cback, "Summary title")
                await interactions.response.send_modal(modal)
            else:
                await interactions.response.send_message(f'You need to select a watched calendar before confirming.', ephemeral=True)
            
           
    return MakeSummaryForm()
############################## END VIEWS ##############################
