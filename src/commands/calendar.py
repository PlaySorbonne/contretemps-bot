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

from discord.ext import tasks, pages, commands

from event_notifier import EventNotifier
from google_calendar import GoogleAuthentifier

import datetime
import dateutil
import functools


from .interactions.calendar import \
    ConnectModal, ConnectView, AddWatchForm, MakeSummaryForm
from .interactions.common import DangerForm
from .interactions.common import access_control
from bot import server_notifiers




async def get_notifier_names(ctx):
    return server_notifiers[ctx.interaction.guild.id].get_watches_names()
async def get_summary_names(ctx):
    watch_id = ctx.options['notifier']
    return server_notifiers[ctx.interaction.guild.id].get_summaries_names(watch_id)

################################ SLASH COMMANDS ################################

class CalendarCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_member = None
    
    @commands.slash_command(description="Connect to Google Agenda.")
    @access_control(2)
    async def connect(self, ctx):
        x = GoogleAuthentifier()
        message = "Get the code at this url then click the button. " + x.get_url()
        email = server_notifiers[ctx.guild.id].get_email()
        if email is not None :
            message+=f'\n**Warning : you were connected with the mail {email}.'
            message+='You either need to connect using the same account,'
            message+=' or do delete all the previous things by doing /purge before.**'
        await ctx.respond(content=message, view=ConnectView(ctx.guild.id, x), ephemeral=True)


    @commands.slash_command(description="Add a new calendar watch.")
    @access_control(2)
    async def add_new_event_notifier(self, ctx):
        cals = server_notifiers[ctx.guild.id].get_all_calendars()
        if (server_notifiers[ctx.guild.id].connected):
            await ctx.respond("Adding new watch...", view=AddWatchForm(ctx.guild, cals), ephemeral=True)
        else:
            await ctx.respond("You are not connected to GoogleAgenda, do /connect", ephemeral=True)




    @commands.slash_command(description="Show a summary of watched events.")
    @access_control(1)
    async def make_summary(self, ctx):
        if (server_notifiers[ctx.guild.id].connected):
            await ctx.respond("", view=MakeSummaryForm(ctx.guild), ephemeral=True)
        else:
            await ctx.respond("You are not connected to GoogleAgenda, do /connect", ephemeral=True)



    @commands.slash_command(description="0 for no access, 1 for editings notifiers, 2 for managing access")
    @access_control(2)
    async def set_access(self,
        ctx,
        who : discord.Option[discord.SlashCommandOptionType.mentionable],
        level : discord.Option[int]
    ):
        if level < 0 or level > 2:
            await ctx.respond(f'{level} is not a valid level. 0, 1 and 2 are the only valid ones.', ephemeral=True)
        else:
            server_notifiers[ctx.guild.id].set_access(who.id, who.mention, level)
            await ctx.respond(f'Set up access level {level} for {who.mention}', ephemeral=True)

    @commands.slash_command(description="Show all the access rules")
    @access_control(2)
    async def list_access(self, ctx):
        lvls = server_notifiers[ctx.guild.id].list_access_levels()
        emoji = { 1 : ':green_square:', 2 : ':red_square:' }
        ld = { 1 : 'editing notifiers (1)', 2 : 'all rights (2)' }
        desc = '\n'.join(
          f'{emoji[u.access_level]} {u.mention} :  {ld[u.access_level]}'
          for u in lvls
        )
        title = "Access levels"
        await ctx.respond("", embed=discord.Embed(title=title, description=desc), ephemeral=True)




    @commands.slash_command(description="Delete an Event Summary")
    @access_control(1)
    async def delete_summary(self,
        ctx,
        notifier : discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_notifier_names)),
        summary : discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_summary_names))
    ):
        if await server_notifiers[ctx.guild.id].delete_summary(notifier, summary):
            await ctx.respond(f"Succesfully deleted the summary {summary}", ephemeral=True)
        else:
            await ctx.respond(f"No such summary exists.", ephemeral=True)

    @commands.slash_command(description="Delete an Event Notifier")
    @access_control(1)
    async def delete_notifier(self,
        ctx, 
        notifier : discord.Option(str, autocomplete=discord.utils.basic_autocomplete(get_notifier_names))
    ):
        if await server_notifiers[ctx.guild.id].delete_watch(notifier):
            await ctx.respond(f"Succesfully deleted notifier {notifier} and all its summaries", ephemeral=True)
        else:
            await ctx.respond(f"No such notifier", ephemeral=True)


    @commands.slash_command(description="List all notifiers' details")
    @access_control(1)
    async def list_notifiers(self, ctx):
        acc = server_notifiers[ctx.guild.id]
        desc = ""
        embeds = []
        for n in acc.get_all_watches():
            title = f"Event Notifier : {n.watch_id}"
            desc =  f"""**Calendar**: {n.calendar_name}
                        **Channel**: {ctx.guild.get_channel_or_thread(int(n.channel_id))}
                        **Options**: """ \
                  + ("new events/" if n.updates_new else "") \
                  + ("modified events/" if n.updates_mod else "") \
                  + ("cancelled events/" if n.updates_del else "") \
                  + "\n **Associated Summaries** : "
            items = [] #TODO : handle when >= 25 summaries
            for s in acc.get_all_summaries(n.watch_id):
                sday = int(datetime.datetime.fromisoformat(s.base_date).timestamp())
                freq = str(EventNotifier.parse_delta(s.frequency))
                items.append(discord.EmbedField(
                    name=s.summary_id,
                    value=f"**Base date** : <t:{int(sday)}:F>\n**Frequency**: {freq}"
                ))
            embeds.append(discord.Embed(title=title, description = desc, fields=items))
        mypages = [pages.Page(content="", embeds=[e]) for e in embeds]
        if mypages:
            paginator = pages.Paginator(pages=mypages) #TODO : prettier
            await paginator.respond(ctx.interaction, ephemeral=True)
        else:
            await ctx.respond("No notifier found.", ephemeral=True)




    @commands.slash_command(description="Force a check for some change in all summaries")
    @access_control(1)
    async def update_all_summaries(self, ctx):
        await ctx.respond('Updating all summaries...', ephemeral=True)
        await server_notifiers[ctx.guild.id].update_all_summaries()


    @commands.slash_command(description="[DANGEROUS] Delete everything and dissociate google account")
    @access_control(2)
    async def purge(self, ctx):
        async def action():
            await server_notifiers[ctx.guild.id].purge()
        await ctx.respond(
            "# WARNING : THIS WILL DELETE ALL CONFIGS.",
            view=DangerForm(action),
            ephemeral = True
        )

    @commands.slash_command(description="Privacy policy")
    async def privacy_policy(self, ctx):
        await ctx.respond(
          "Privacy policy : https://github.com/PlaySorbonne/contretemps-bot/blob/main/privacy-policy",
          ephemeral = True
        )
 
############################## END SLASH COMMANDS ##############################

