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


import logging
from os import makedirs
from datetime import datetime
from discord import utils, Permissions
from bot import bot, server_notifiers
from commands import calendar, tasker
from event_notifier import EventNotifier
from commands.interactions.tasker import TaskInteractView


############################## LOGGER SETUP ###################################
logger = logging.getLogger(__name__)
numeric_level = logging.INFO #TODO: make it a command line argument
launched_at = datetime.now().strftime("%Y%m%d-%H%M%S")
makedirs('./data/logs', exist_ok=True)
logging.basicConfig(
  filename='data/logs/log-'+launched_at,
  level=numeric_level,
  format='%(levelname)s:[%(asctime)s]:'
         +'[%(filename)s::%(funcName)s]:  %(message)s'
)
############################ END LOGGER SETUP #################################


################################ BOT SETUP ####################################
################################ FETCH TOKENS #################################
from os import environ
if 'CONTRETEMPS_DISCORD_TOKEN' in environ and 'CONTRETEMPS_CLIENT_ID' in environ:
  token = environ['CONTRETEMPS_DISCORD_TOKEN']
  client_id = environ['CONTRETEMPS_CLIENT_ID']
else:
  import env
  token = env.DISCORD_TOKEN
  client_id = env.CLIENT_ID
########################### END FETCH TOKENS ##################################

################################ BOT SETUP ####################################
# Setting up an EventNotifier for each server the bot is a member of
@bot.event
async def on_ready():
    async for guild in bot.fetch_guilds(limit=150):
        server_notifiers[guild.id] = EventNotifier(guild.id, guild.name, bot)
    bot.add_view(TaskInteractView())
@bot.event
async def on_guild_join(guild):
    server_notifiers[guild.id] = EventNotifier(guild.id, guild.name, bot)

@bot.event
async def on_guild_remove(guild):
    pass # do we delete the guild configuration or just keep it ?

bot.add_cog(calendar.CalendarCommands(bot))
bot.add_cog(tasker.TaskerCommands(bot))
############################## END BOT SETUP ##################################

################################ BOT LAUNCH ###################################
oauth = utils.oauth_url(
  client_id,
  permissions=Permissions(18135567026240),
  scopes=('bot', 'guilds.members.read'),
)
print("URL:", oauth)
logger.info("STARTING BOT...")
bot.run(token)
logger.info("BOT STOPPED")
############################## END BOT LAUNCH #################################
