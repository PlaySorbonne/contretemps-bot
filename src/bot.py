
import discord

from discord.ext import tasks

from event_notifier import EventNotifier
from google_calendar import GoogleAuthentifier

from threading import Event, get_ident

import datetime


token = open('.env', 'r').read()


bot = discord.Bot()

server_notifiers = dict()

@bot.event
async def on_ready():
    async for guild in bot.fetch_guilds(limit=150):
        server_notifiers[guild.id] = EventNotifier(guild.id, bot)

#TODO on_join_guild et on_ban_de_guild
#TODO TODO add roles and permissions : not anyone should be able to do the thing



class ConnectModal(discord.ui.Modal):
    def __init__(self, gid, x, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.__x = x
        self.gid = gid
        
        self.add_item(discord.ui.InputText(label="Enter the authentification code: ", style=discord.InputTextStyle.long))
    
    async def callback(self, interaction):
        #embed = discord.Embed(title="Modal results")
        #embed.add_field(name="Long Input", value=self.children[0].value)
        creds = self.__x.get_credentials(self.children[0].value)
        #print(server_notifiers, "SNN")
        #print(self.gid)
        #TODO : clear everything from old connection if we reconnect
        mail = server_notifiers[self.gid].connect(creds, [])
        await interaction.response.send_message(f"Connected succesfully as {mail}", ephemeral=True)

def ConnectView(guildid, x):
    class ConnectView(discord.ui.View):
        @discord.ui.button(label="I got the code", style=discord.ButtonStyle.primary)
        async def button_callback(self, button, interaction):
            modal = ConnectModal(guildid,x, title="Authentification code")
            await interaction.response.send_modal(modal)
    return ConnectView()

@bot.slash_command(description="Connect to Google Agenda.")
async def connect(ctx):
    x = GoogleAuthentifier()
    await ctx.respond("Get the code at this url then click the button. " + x.get_url(), view=ConnectView(ctx.guild.id, x), ephemeral=True)



def AddWatchForm(guild):
    gid = guild.id
    cals = server_notifiers[gid].get_all_calendars()
    channels = guild.channels
    class AddWatchForm(discord.ui.View):
        
        def __init__(self):
            super().__init__()
            self.channel = None
            self.cal = None
            self.upd_new = True
            self.upd_del = True
            self.upd_mod = True
            
        
        @discord.ui.select(
            placeholder = "Choose a calendar",
            min_values=1,
            max_values=1,
            options = [ discord.SelectOption(label=e['name'], value=e['id']) for e in cals ],
            row=0
        )
        async def select_callback_1(self, select, interaction):
            self.cal = select.values[0]
            only_val = [so.label for so in select.options if so.value == self.cal][0]
            select.placeholder = only_val
            await interaction.response.edit_message(view=self)
            #await interaction.response.send_message(f"You have chosen  {select.values[0]}.")
        
        @discord.ui.select(
            placeholder = "Choose a channel",
            min_values=1,
            max_values=1,
            options = [ discord.SelectOption(label=c.name, value=str(c.id)) for c in channels ],
            row=1
        )
        async def select_callback_2(self, select, interaction):
            self.channel = select.values[0]
            only_val = [so.label for so in select.options if so.value == self.channel][0]
            select.placeholder = only_val
            await interaction.response.edit_message(view=self)
            #await interaction.response.send_message(f"You have chosen  {select.values[0]}.")
        
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
                server_notifiers[gid].add_watch(self.channel, self.cal, self.upd_new, self.upd_mod, self.upd_del)
                await interactions.response.send_message(content=f'It sould be done now !') #TODO put info of new watch in content
                await self.message.delete()
            else:
                await interactions.response.send_message(f'You need to select a calendar and a channel before confirming.', ephemeral=True)
            
           
    return AddWatchForm()

@bot.slash_command(description="Add a new calendar watch.")
async def add_new_event_notifier(ctx):
    if (server_notifiers[ctx.guild.id].connected):
        await ctx.respond("Adding new watch...", view=AddWatchForm(ctx.guild), ephemeral=True) #TODO : NAMED COMMAND
    else:
        await ctx.respond("You are not connected to GoogleAgenda, do /connect")



def ActionModal(lbl, cback, title):
    class ActionModal(discord.ui.Modal):
        def __init__(self):
            super().__init__(title=title)
            
            self.add_item(discord.ui.InputText(label=lbl, style=discord.InputTextStyle.long))
        
        callback = cback
    return ActionModal()

def MakeSummaryForm(guild):
    gid = guild.id
    cals = server_notifiers[gid].get_all_watched_cals()
    formated = []
    for c in cals:
        cname = bot.get_channel(int(c['channel_id'])).name
        calname = c['calendar_name']
        formated.append('#'+cname+'---'+calname)
    today = datetime.date.today()
        
        
    class MakeSummaryForm(discord.ui.View):
        
        def __init__(self):
            super().__init__()
            self.watched_cal = None
            self.duration = 7
            self.in_months = 0
            self.base_day = today
            self.header = "" # TODO : Header !!
            
        
        @discord.ui.select(
            placeholder = "Choose a watched calendar",
            min_values=1,
            max_values=1,
            options = [ discord.SelectOption(label=formated[i], value=str(i)) for i in range(len(cals)) ], #TODO if watched cals more than 25
            row=0
        )
        async def select_callback_1(self, select, interaction):
            i = select.values[0]
            self.watched_cal = cals[int(i)]
            select.placeholder = formated[int(i)]
            await interaction.response.edit_message(view=self)
            #await interaction.response.send_message(f"You have chosen  {select.values[0]}.")
        
        @discord.ui.select(
            placeholder = "Starting on day...",
            min_values=1,
            max_values=1,
            options = [ discord.SelectOption(label=(today+datetime.timedelta(days=i)).isoformat(), value=str(i)) for i in range(20) ], #TODO TODO 
            row=1
        )
        async def select_callback_2(self, select, interaction):
            self.base_day = today+datetime.timedelta(days=int(select.values[0]))
            select.placeholder = self.base_day.isoformat()
            await interaction.response.edit_message(view=self)
        
        @discord.ui.select(
            placeholder = "Reset every...",
            min_values=1,
            max_values=1,
            options = [ discord.SelectOption(label=str(i), value=str(i)) for i in range(21) ], #TODO MAKE INTO TEXT
            row=2
        )
        async def select_callback_10(self, select, interaction):
            self.duration = (select.values[0])
            select.placeholder = str(select.values[0])
            await interaction.response.edit_message(view=self)        
        
        @discord.ui.button(label="Duration in days", style=discord.ButtonStyle.primary, row=3)
        async def select_callback_3(self, button, interactions):
            if self.in_months == 0:
                button.label="Duration in months"
                self.in_months = 1
            else:
                button.label="Duration in days"
                self.in_months = 0
            await interactions.response.edit_message(view=self)


        @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, row=4)
        async def select_callback_6(self, button, interactions):
            if self.watched_cal is not None:
                async def cback(self2, interaction):
                    hey = self2.children[0].value
                    if not server_notifiers[gid].check_summary_uniqueness(hey):
                        await self.message.edit('A summary with that name already exists...')
                        await interaction.response.defer()
                    else : 
                        server_notifiers[gid].add_summary(self.watched_cal, self.duration, self.in_months, self.base_day, hey) 
                        await self.message.delete()
                        await interaction.response.send_message(f'Succesfully added summary', ephemeral=True)
                modal = ActionModal("Please enter a summary title which is unique", cback, "Summary title")
                await interactions.response.send_modal(modal)
            else:
                await interactions.response.send_message(f'You need to select a watched calendar before confirming.', ephemeral=True)
            
           
    return MakeSummaryForm()


@bot.slash_command(description="Show a summary of watched events.")
async def make_summary(ctx):
    if (server_notifiers[ctx.guild.id].connected):
        await ctx.respond("", view=MakeSummaryForm(ctx.guild))



bot.run(token)


