
import discord

from discord.ext import tasks

from event_notifier import EventNotifier
from google_calendar import GoogleAuthentifier


token = open('.env', 'r').read()


bot = discord.Bot()

server_notifiers = dict()

@bot.event
async def on_ready():
    async for guild in bot.fetch_guilds(limit=150):
        server_notifiers[guild.id] = EventNotifier(guild.id, bot)

#TODO on_join_guild et on_ban_de_guild



class ConnectModal(discord.ui.Modal):
    def __init__(self, gid, x, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.__x = x
        self.gid = gid
        
        self.add_item(discord.ui.InputText(label="Enter something bliz : ", style=discord.InputTextStyle.long))
    
    
    async def callback(self, interaction):
        #embed = discord.Embed(title="Modal results")
        #embed.add_field(name="Long Input", value=self.children[0].value)
        creds = self.__x.get_credentials(self.children[0].value)
        #print(server_notifiers, "SNN")
        #print(self.gid)
        server_notifiers[self.gid].connect(creds)
        await interaction.response.send_message("Connected succesfully!!" )


def ConnectView(guildid, x):
    class ConnectView(discord.ui.View):
        @discord.ui.button(label="Enter the link, then click !", style=discord.ButtonStyle.primary)
        async def button_callback(self, button, interaction):
            modal = ConnectModal(guildid,x, title="Heheheheheehhe")
            await interaction.response.send_modal(modal)
    return ConnectView()


def AddWatchForm(guild):
    gid = guild.id
    cals = server_notifiers[gid].get_all_calendars()
    channels = guild.channels
    class AddWatchForm(discord.ui.View):
        @discord.ui.select(
            placeholder = "Choose a calendar",
            min_values=1,
            max_values=1,
            options = [ discord.SelectOption(label=e['name']) for e in cals ]
        )
        async def select_callback(self, select, interaction):
            await interaction.response.send_message(f"You have chosen  {select.values[0]}.")
    return AddWatchForm

@bot.slash_command(description="Add a new calendar watch.")
async def add_new_watch(ctx):
    if (server_notifiers[ctx.guild.id].connected):
        await ctx.respond("Adding new watch...", view=AddWatchForm(ctx.guild)())
    else:
        await ctx.respond("You are not connected to GoogleAgenda, do /connect")

@bot.slash_command(description="Connect to Google Agenda.")
async def connect(ctx):
    x = GoogleAuthentifier()
    await ctx.respond("Get the code at this url then click the button ! " + x.get_url(), view=ConnectView(ctx.guild.id, x), ephemeral=True)


bot.run(token)


