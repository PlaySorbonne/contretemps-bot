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
from bot import server_notifiers

import datetime
import dateutil
import functools



###################### GENERIC/COMMON PARTS FOR COMMANDS ######################
def access_control(lvl):
    """
    Decorator that protects a command under some access level
    Levels range from 0 to 2:
      - 0 for a command needing no privilege
      - 1 for commands setting up and configuring the notifier
      - 2 for handling access levels of other members
    """
    def dec(f):
        @functools.wraps(f)
        async def new_f(self, ctx: discord.ApplicationContext, *args, **kwargs):
            l = server_notifiers[ctx.guild.id].get_access_level(ctx.author)
            if ctx.author == ctx.guild.owner or l >= lvl :
                await f(self, ctx, *args, **kwargs)
            else:
                await ctx.respond(f"This command requires an an access level of {lvl}, but you have {l}.", ephemeral=True)
        return new_f
    return dec 


def ActionModal(lbl, cback, title):
    """
    Generic reframing of a Modal allowing to 
    specify the action taken with the text entered
    as a parameter in the "constructor"
    """
    class ActionModal(discord.ui.Modal):
        def __init__(self):
            super().__init__(title=title)
            
            self.add_item(discord.ui.InputText(label=lbl, style=discord.InputTextStyle.long))
        
        callback = cback
    return ActionModal()


def paginated_selector(name, options, to_str, row, page_len=23):
    """
    Decorator for making a Select Component that can take more
    than 25 options by splitting them into multiple parts  
    """
    def to_str2(e, i, l): # helper function
        if i == 0 or i == l-1: return e
        return to_str(e)
    
    n = (len(options)-1)//page_len + 1 if options else 1
    options = [
        [f'Goto page {i}/{n}']+options[i*page_len:(i+1)*page_len]+[f'Goto page {i+2}/{n}']
        for i in range(n)
    ]
    options[0][0], options[-1][-1] = f'First page of {n}', f'Last page of {n}'
    
    def make_options(p_n):
        return [
            discord.SelectOption(
                label=to_str2(options[p_n][i], i, len(options[p_n])),
                value=str(i)
            )
            for i in range(len(options[p_n])) 
        ]
    
    def decorator(f):
        current_page = [0]
        @discord.ui.select(
            placeholder = f"Choose a {name}",
            min_values=1, max_values=1,
            options=make_options(0),
            row=row
        )
        async def new_f(self, select, interaction):
            i = int(select.values[0])
            if i == 0:
                if (current_page[0] == 0): # we stay on the first page
                    await interaction.response.defer()
                else:
                    current_page[0] -= 1
                    select.options = make_options(current_page[0])
                    await interaction.response.edit_message(view=self)
            elif i == len(options[current_page[0]])-1:
                if (current_page[0] == n - 1):
                    await interaction.response.defer()
                else:
                    current_page[0] += 1
                    select.options = make_options(current_page[0])
                    await interaction.response.edit_message(view=self)
            else :
                await f(self, select, interaction, options[current_page[0]][i])
        return new_f
    return decorator



class DangerForm(discord.ui.View):
    def __init__(self, action):
        self.action = action
        super().__init__()
    @discord.ui.button(
        label='CONFIRM (BE CAREFUL PLEASE)',
        style=discord.ButtonStyle.danger
    )
    async def button_callback(self, button, interaction):
        async def cback(self2, interaction2):
            if self2.children[0].value == 'YES I AM SURE':
                await self.action()
                await interaction2.response.send_message("Succeeded.", ephemeral=True)
                await self.message.delete()
            else:
                await interaction2.response.send_message("Bad confirmation", ephemeral=True)
                await self.message.delete()
        modal = ActionModal('DANGER', cback, "WRITE 'YES I AM SURE' TO CONFIRM")
        await interaction.response.send_modal(modal)

################### END GENERIC/COMMON PARTS FOR COMMANDS #####################
