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

import datetime
import dateutil
import functools




#TODO : restucture (and split) this file into multiple files
#### until there is a claner and more logical structure for the contents ####
#### of this file, I'll use comments like this to make it less unreadable####




################################ BOT SETUP ####################################
bot = discord.Bot()

server_notifiers = dict() # Maps each server (using its id) to an EventNotifier

# Setting up an EventNotifier for each server the bot is a member of
@bot.event
async def on_ready():
    async for guild in bot.fetch_guilds(limit=150):
        server_notifiers[guild.id] = EventNotifier(guild.id, guild.name, bot)

@bot.event
async def on_guild_join(guild):
    server_notifiers[guild.id] = EventNotifier(guild.id, guild.name, bot)

@bot.event
async def on_guild_remove(guild):
    pass # do we delete the guild configuration or just keep it ?
############################## END BOT SETUP ##################################




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
        async def new_f(ctx: discord.ApplicationContext, *args, **kwargs):
            l = server_notifiers[ctx.guild.id].get_access_level(ctx.author)
            if ctx.author == ctx.guild.owner or l >= lvl :
                await f(ctx, *args, **kwargs)
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
    
    n = (len(options)-1)//page_len + 1
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




################################ SLASH COMMANDS ################################
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

@bot.slash_command(description="Connect to Google Agenda.")
@access_control(2)
async def connect(ctx):
    x = GoogleAuthentifier()
    message = "Get the code at this url then click the button. " + x.get_url()
    email = server_notifiers[ctx.guild.id].get_email()
    if email is not None :
        message+=f'\n**Warning : you were connected with the mail {email}.'
        message+='You either need to connect using the same account,'
        message+=' or do delete all the previous things by doing /purge before.**'
    await ctx.respond(content=message, view=ConnectView(ctx.guild.id, x), ephemeral=True)



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

@bot.slash_command(description="Add a new calendar watch.")
@access_control(2)
async def add_new_event_notifier(ctx):
    cals = server_notifiers[ctx.guild.id].get_all_calendars()
    if (server_notifiers[ctx.guild.id].connected):
        await ctx.respond("Adding new watch...", view=AddWatchForm(ctx.guild, cals), ephemeral=True)
    else:
        await ctx.respond("You are not connected to GoogleAgenda, do /connect", ephemeral=True)




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


@bot.slash_command(description="Show a summary of watched events.")
@access_control(1)
async def make_summary(ctx):
    if (server_notifiers[ctx.guild.id].connected):
        await ctx.respond("", view=MakeSummaryForm(ctx.guild), ephemeral=True)
    else:
        await ctx.respond("You are not connected to GoogleAgenda, do /connect", ephemeral=True)



@bot.slash_command(description="0 for no access, 1 for editings notifiers, 2 for managing access")
@access_control(2)
async def set_access(
    ctx,
    who : discord.Option(discord.SlashCommandOptionType.mentionable),
    level : discord.Option(int)
):
    if level < 0 or level > 2:
        await ctx.respond(f'{level} is not a valid level. 0, 1 and 2 are the only valid ones.', ephemeral=True)
    else:
        server_notifiers[ctx.guild.id].set_access(who.id, who.mention, level)
        await ctx.respond(f'Set up access level {level} for {who.mention}', ephemeral=True)

@bot.slash_command(description="Show all the access rules")
@access_control(2)
async def list_access(ctx):
    lvls = server_notifiers[ctx.guild.id].list_access_levels()
    emoji = { 1 : ':green_square:', 2 : ':red_square:' }
    ld = { 1 : 'editing notifiers (1)', 2 : 'all rights (2)' }
    desc = '\n'.join(
      f'{emoji[u["access_level"]]} {u["mention"]} :  {ld[u["access_level"]]}'
      for u in lvls
    )
    title = "Access levels"
    await ctx.respond("", embed=discord.Embed(title=title, description=desc), ephemeral=True)




async def get_notifier_names(ctx):
    return server_notifiers[ctx.interaction.guild.id].get_watches_names()
async def get_summary_names(ctx):
    watch_id = ctx.options['notifier']
    return server_notifiers[ctx.interaction.guild.id].get_summaries_names(watch_id)

@bot.slash_command(description="Delete an Event Summary")
@access_control(1)
async def delete_summary(
    ctx,
    notifier : discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_notifier_names)),
    summary : discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_summary_names))
):
    if await server_notifiers[ctx.guild.id].delete_summary(notifier, summary):
        await ctx.respond(f"Succesfully deleted the summary {summary}", ephemeral=True)
    else:
        await ctx.respond(f"No such summary exists.", ephemeral=True)

@bot.slash_command(description="Delete an Event Notifier")
@access_control(1)
async def delete_notifier(
    ctx, 
    notifier : discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_notifier_names))
):
    if await server_notifiers[ctx.guild.id].delete_watch(notifier):
        await ctx.respond(f"Succesfully deleted notifier {notifier} and all its summaries", ephemeral=True)
    else:
        await ctx.respond(f"No such notifier", ephemeral=True)


@bot.slash_command(description="List all notifiers' details")
@access_control(1)
async def list_notifiers(ctx):
    acc = server_notifiers[ctx.guild.id]
    desc = ""
    embeds = []
    for n in acc.get_all_watches():
        title = f"Event Notifier : {n['watch_id']}"
        desc =  f"""**Calendar**: {n['calendar_name']}
                    **Channel**: {ctx.guild.get_channel_or_thread(int(n['channel_id']))}
                    **Options**: """ \
              + ("new events/" if n['updates_new'] else "") \
              + ("modified events/" if n['updates_mod'] else "") \
              + ("cancelled events/" if n['updates_del'] else "") \
              + "\n **Associated Summaries** : "
        items = [] #TODO : handle when >= 25 summaries
        for s in acc.get_all_summaries(n['watch_id']):
            sday = int(datetime.datetime.fromisoformat(s['base_date']).timestamp())
            freq = str(EventNotifier.parse_delta(s['frequency']))
            items.append(discord.EmbedField(
                name=s['summary_id'],
                value=f"**Base date** : <t:{int(sday)}:F>\n**Frequency**: {freq}"
            ))
        embeds.append(discord.Embed(title=title, description = desc, fields=items))
    mypages = [pages.Page(content="", embeds=[e]) for e in embeds]
    if mypages:
        paginator = pages.Paginator(pages=mypages) #TODO : prettier
        await paginator.respond(ctx.interaction, ephemeral=True)
    else:
        await ctx.respond("No notifier found.", ephemeral=True)




@bot.slash_command(description="Force a check for some change in all summaries")
@access_control(1)
async def update_all_summaries(ctx):
    await server_notifiers[ctx.guild.id].update_all_summaries()
    await ctx.respond('Finished updating all summaries', ephemeral=True)


@bot.slash_command(description="[DANGEROUS] Delete everything and dissociate google account")
@access_control(2)
async def purge(ctx):
    async def action():
        await server_notifiers[ctx.guild.id].purge()
    await ctx.respond(
        "# WARNING : THIS WILL DELETE ALL CONFIGS.",
        view=DangerForm(action),
        ephemeral = True
    )
    
############################## END SLASH COMMANDS ##############################


#TODO : Command allowing to EDIT notifiers and summaries
#TODO : force update all summaries of server
#TODO : restrict to only guilds (or handle non Member user objects (no roles)
# note to self : autocomplete for slash commands gives max 25 choices


################################ BOT LAUNCH ###################################
token = open('.discord_token', 'r').read()
bot.run(token)
############################## END BOT LAUNCH #################################

