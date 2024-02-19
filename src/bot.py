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




#TODO : Command allowing to EDIT notifiers and summaries
#TODO : force update all summaries of server
#TODO : restrict to only guilds (or handle non Member user objects (no roles)
# note to self : autocomplete for slash commands gives max 25 choices



