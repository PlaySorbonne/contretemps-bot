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


from database.tools import get_or_create, select, detached_copy
from database import calendar as DB, Session, engine

from discord.ext import tasks
from discord import Embed, EmbedField
from discord.errors import NotFound

from google_calendar import CalendarApiLink
from utils import signalEntryExitAsync, LogAdapter

import datetime
from datetime import timezone, timedelta
from dateutil.relativedelta import relativedelta
from dateutil.utils import within_delta

import asyncio
import sys
if sys.version_info >= (3, 11):
    from asyncio import timeout
else:
    from async_timeout import timeout

import logging
logger = logging.getLogger(__name__)

#TODO : handle timezones correctly everywhere
#TODO : now it is hardcoded to just work with UTC+1
UTC = timezone.utc


class EventNotifier:

    def __init__(self, server_id, server_name, bot):
        self.__b = bot
        self.__server_id = server_id
        self.__name = server_name
        self.__log = LogAdapter(logger, {"server": server_name})
        with Session(engine) as session:
            state = get_or_create(session, DB.ServerConnexion, server_id=server_id)
            self.__link, self.connected = None, False
            self.__email = state.gmail
            self.connect(state.gtoken)
            self.check_summaries.start()
            session.commit()
        print("Succesfully configured", self.__name, self.__server_id)
        
        
    def connect(self, tok):
      with Session(engine) as s, s.begin():
        server = s.get(DB.ServerConnexion, self.__server_id)
        if (tok):
            try:
                new_link = CalendarApiLink(tok, [], self.update)
                new_mail = new_link.get_email()
                if self.__email is None or self.__email == new_mail:
                    self.__link, self.connected = new_link, True
                    self.__email = new_mail
                    server.gtoken, server.gmail = tok, self.__email
                    for cal in server.watches:
                      self.__link.watch_calendar(cal.calendar_id)
                    return True, self.__email
                return False, f'New account ({new_mail}) different from old ({self.__email})'
            except CalendarApiLink.BadCredentials:
                server.gtoken, server.gmail = None, self.__email
                return False, "bad credentials for connection."
        else:
            return False, 'bad connection code'
    
    async def purge(self):
      with Session(engine, autoflush=False) as d, d.begin():
        server = d.get(DB.ServerConnexion, self.__server_id)
        for w in server.watches:
            await self.delete_watch(w.watch_id, d=d)
        server.gtoken, server.gmail = None, None
        self.__email, self.__link, self.connected = None, None, False
    
    def get_email(self):
        return self.__email
    
    async def add_watch(self, channel_id, cal, new, dele, mod, name):
        with Session(engine) as s, s.begin():
            new_watch = DB.WatchedCalendar(
              server_id = self.__server_id,
              watch_id = name,
              channel_id = channel_id,
              updates_new = new,
              updates_mod = mod,
              updates_del = dele,
              calendar_id = cal['id'],
              calendar_name = cal['name']
            )
            s.add(new_watch)
        
        r = self.safe_calendar_call(
            lambda : self.__link.watch_calendar(cal['id'])
        )
        if not r:
            await self.__b.get_channel(int(channel_id)).send(
              "Warning : I am disconnected from the Google Account",
              delete_after=60
            )
        
    
    def get_all_watched_cals(self):
        with Session(engine) as s:
            return s.get(DB.ServerConnexion, self.__server_id).watches
        
    
    async def update(self, modifs):
      if (self.__link is None):
          return
      #TODO handle timezones ?
      with Session(engine) as d, d.begin():
        for cal in modifs:
            for watched in d.scalars(select(DB.WatchedCalendar).filter_by(server_id=self.__server_id, calendar_id=cal)):
                for e in modifs[cal]:
                    if not True : #TODO self.filter_tags(e['tags'], watched['filter']):
                        continue

                    
                    change = None
                    if e['status'] == 'cancelled' :
                        if watched.updates_del:
                            change = 'del'
                    elif within_delta(
                        datetime.datetime.fromisoformat(e['updated'][:-1]),
                        datetime.datetime.fromisoformat(e['created'][:-1]),
                        datetime.timedelta(seconds=2)
                         ):
                        if watched.updates_new:
                            change = 'new'
                    else: # Event modified
                        if watched.updates_mod:
                            change = 'mod'
                    if change:
                        u = await self.__b.get_channel(int(watched.channel_id)).send(
                          "",
                          embed=EventNotificationEmbed(e, change)
                        )
                        # TODO : store this message and delete it when new update / when the watch is deleted
                # Handling all the summaries attached to the watch
                summaries = watched.summaries
                for s in summaries:
                    await self.update_summary_message(s, d=d)
    
    
    @tasks.loop(seconds=5)
    @signalEntryExitAsync(logger=logger)
    async def check_summaries(self):
      if (self.__link is None):
          self.__log.info(f"Exiting after no link with server.")
          return #TODO : maybe message the admins at least one time ?
      self.__log.info(f'Start cheking summaries.')
      with Session(engine) as d, d.begin(): #TODO : CHECK THIS
        for w in d.get(DB.ServerConnexion, self.__server_id).watches:
            self.__log.info(f'Cheking watch "{w.watch_id}"')
            for s in w.summaries:
                # check if it is time to update the summary base date
                #TODO : handle these ad-hoc conversions using sqlalchemy's types (for dates and maybe for discord snowflakes ?)
                base_date = EventNotifier.iso_to_utcdt(s.base_date)
                delta = EventNotifier.parse_delta(s.frequency)
                now = datetime.datetime.now().replace(tzinfo=UTC)
                self.__log.info(
                    f'Cheking summary "{s.summary_id}".'
                    +f'(base={base_date}, delta={delta},'
                    +f' now={now}). Fetching message list from Discord API...'
                )
                m = await self.fetch_message_list_opt(w.channel_id, s.message_id)
                self.__log.info(
                    f'Finished awaiting message list for "{s.summary_id}"'
                )
                bad_message = now > base_date + delta
                if (bad_message):
                    self.__log.info(f'Found finished summary "{s.summary_id}"')
                    while (now > base_date+delta):
                        base_date += delta
                bad_message = bad_message or m is None or\
                              (m[0].created_at+timedelta(hours=1)) < base_date and base_date <= now
                if bad_message:
                    s.base_date = base_date.isoformat()
                    #TODO : possible race condition here is message gets deleted from db just before this ?
                    self.__log.info(f'Preparing to delete and republish "{s.summary_id}"')
                    await self.delete_summary_message(s, d=d)
                    await self.publish_summary(s, d=d)
                    self.__log.info(f'Finished republishings "{s.summary_id}"')
    
    async def delete_watch(self, watch_id, d=None):
        if d is None :
          with Session(engine,autoflush=False) as d, d.begin():
            return await self.delete_watch(watch_id, d)
        w = d.get(DB.WatchedCalendar, (self.__server_id, watch_id))
        if w is None:
            return False
        S = w.summaries
        for s in S:
            await self.delete_summary(watch_id, s.summary_id, d=d) # redundant requests :[[ Not anymore !!
        d.delete(w)
        return True
    
    async def delete_summary(self, watch_id, summary_id, d=None):
        if d is None:
          with Session(engine) as d, d.begin():
            return await self.delete_summary(watch_id, summary_id, d=d)
        s = d.get(DB.EventSummary,
                  {'summary_id' : summary_id, 'watch_id' : watch_id,
                   'server_id': self.__server_id})
        if s is None: #TODO proper logging
            print(f"Did not find summary {summary_id}")
            return False
        await self.delete_summary_message(s, upd_db=False, d=d)
        d.delete(s)
        return True
    
    async def clear_summaries(self, watch_id, d=None):
        if d is None:
          with Session(engine) as d, d.begin():
            return await self.clear_summaries(watch_id,d)
        for s in d.get(DB.WatchedCalendar, (self.__server_id, watch_id)).summaries:
            await self.delete_summary(s.watch_id, s.summary_id, d) #redundant db requests :[ NOT ANYMORE HAHAHAHA
    
    async def delete_summary_message(self, summary, upd_db=False, d=None):
        if d is None:
          with Session(engine) as d, d.begin():
            return await self.delete_summary_message(summary, upd_db, d)
        d.add(summary)
        watch = summary.watch
        if summary.message_id is not None:
             for mid in summary.message_id.split(';'):
                 try:
                    ch = self.__b.get_channel(int(watch.channel_id))
                    if ch is not None:
                        m = (await ch.fetch_message(int(mid)))
                        if (m.author == self.__b.user): #should be always true but extra check since we're deleting a message
                            await m.delete()
                    else:
                        print(f"Did not find channel {watch['channel_id']}. (watch={watch['watch_id']})")
                 except NotFound: #message does not exist anymore, nothing to do
                    print("Tried to delete message from server, but it did not exist :((((")
        if (upd_db):
            summary.message_id = None
    
    async def update_summary_message(self, summary, d=None):
        if d is None:
          with Session(engine) as d, d.begin():
            return await self.update_summary_message(self, summary, d)
        d.add(summary)
        watch = summary.watch
        
        new_evs = self.get_summary_events(summary)
        if (new_evs is None):
            await self.__b.get_channel(int(watch.channel_id)).send(
              f'Warning : I am disconnected from Google, summary {summary.summary_id} not updated'
            )
            return
        m = await self.fetch_message_list_opt(watch.channel_id, summary.message_id)
        await self.publish_summary(summary, m=m, d=d, new_evs = new_evs)


    async def update_all_summaries(self):
      with Session(engine) as d, d.begin():
        for w in d.get(DB.ServerConnexion, self.__server_id).watches:
            for s in w.summaries:
                await self.update_summary_message(s, d=d)


    async def publish_summary(self, summary, m=None, watch=None , d=None, new_evs=None): #TODO remove watch
        if d is None:
          with Session(engine) as s, s.begin():
            return await self.publish_summary(summary, m, watch, s, new_evs)
        d.add(summary) # we assume summary is attached to d
        watch = summary.watch
        if new_evs is None:
            new_evs = self.get_summary_events(summary)
            if (new_evs is None):
                await self.__b.get_channel(int(watch['channel_id'])).send(
                    f'Warning : I am disconnected from Google, summary {summary["summary_id"]} cannot be published'
                )
                return
        content = '# ' + summary.summary_id + '\n' + (summary.header or '')
        new_embd = self.make_daily_embed("", "", new_evs)
        if m is None or len(new_embd) > len(m):
            if m : await self.delete_summary_message(summary, upd_db=False, d=d)
            ms = [await self.__b.get_channel(int(watch.channel_id)).send(content=content, embed=new_embd[0])]
            for embed in new_embd[1:]:
                ms.append(await self.__b.get_channel(int(watch.channel_id)).send(content='', embed=embed))
            summary.message_id = ';'.join(str(m.id) for m in ms)
        else:
            for i in range(len(new_embd)):
                await m[i].edit(content=('' if i>0 else content), embed=new_embd[i])
            for i in range(len(new_embd), len(m)):
                if (m[i].embeds):
                    await m[i].edit(content=('.' if i else content),embeds=[])
    
    def get_all_calendars(self):
        """
        Returns all the calendars that are currently watched in the server
        If the google connexion is no longer valid, returns None
        """
        return self.safe_calendar_call(lambda:self.__link.get_calendars())          
    
    def get_all_watches(self):
      with Session(engine, expire_on_commit=False) as d, d.begin():
        return d.get(DB.ServerConnexion, self.__server_id).watches
        
    def get_all_summaries(self, watch_id):
      with Session(engine, expire_on_commit=False) as d, d.begin():
        return d.get(DB.WatchedCalendar, (self.__server_id, watch_id)).summaries
    
    
    def check_summary_uniqueness(self, watch_id, new_name):
      with Session(engine) as d:
        return d.get(DB.EventSummary, (self.__server_id, watch_id, new_name)) is None
    def check_watch_uniqueness(self, new_name):
      with Session(engine) as d:
        return d.get(DB.WatchedCalendar,(self.__server_id, new_name)) is None
    
    async def add_summary(self, watch_cal, duration, in_months, base_day, header, name):
        base_day_repr = base_day.isoformat()
        duration = relativedelta(months=duration) if in_months else relativedelta(days=duration)
        new_summary = DB.EventSummary(
            server_id = self.__server_id,
            watch_id = watch_cal.watch_id,
            summary_id = name,
            base_date = base_day_repr,
            frequency = repr(duration),
            header = header,
            message_id = None
        )
        with Session(engine) as s, s.begin():
          s.add(new_summary), s.flush() # flush to populate new_summary.watch
          events = self.get_summary_events(new_summary)
          if (events is None):
              await self.__b.get_channel(int(watch_cal.channel_id)).send(
                f'Warning : I am disconnected from Google, summary {name} not published'
              )
              # We remember the summary for future publication
              return
          s.add(new_summary)
        await self.publish_summary(new_summary)
        
    
    def get_watches_names(self):
      with Session(engine) as d:
        W = d.get(DB.ServerConnexion,self.__server_id).watches
        return [w.watch_id for w in W]
    
    def get_summaries_names(self, watch_id):
      with Session(engine) as d:
        S = d.get(DB.WatchedCalendar, (self.__server_id, watch_id)).summaries
        return [s.summary_id for s in S]
    
    # TODO TODO
    def filter_tags(self, tags, filt):
        return True 
    
    def get_summary_events(self, summary):
        """
        Returns a list of the next events for a summary
        If the connexion to the calendar is no longer valid, returns None
        """
        base_date = datetime.datetime.fromisoformat(summary.base_date)
        locs=dict()
        exec(f'duration = {summary.frequency}', globals(), locs)
        end_date = base_date+locs['duration']
        watch = summary.watch
        events = self.safe_calendar_call(
            lambda : self.__link.get_period_events(watch.calendar_id, base_date, end_date)
        )
        return events
    
    def make_daily_embed(self, title, description, events):
        l = {}
        for e in events: # TODO : Handle(or just ignore) multi-day events
            regular = 'dateTime' in e['start']
            date_field = 'dateTime' if regular else 'date'
            day = datetime.datetime.fromisoformat(e['start'][date_field][:-1])
            day = day.replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=UTC)
            start = datetime.datetime.fromisoformat(e['start'][date_field][:-1]).replace(tzinfo=UTC)
            end = datetime.datetime.fromisoformat(e['end'][date_field][:-1]).replace(tzinfo=UTC)
            if regular :
                self._add_embed_event(e, start, end, day, regular, l)
            else :
                days, k = (end-start+datetime.timedelta(days=1)).days, 1
                while start <= end:
                    self._add_embed_event(e, start, start, start, regular, l, k, days)
                    start += datetime.timedelta(days=1)
                    k += 1
        x = self._make_split_daily_embeds(title, description, l)
        return x
    
    def _make_split_daily_embeds(self, title, description, l):
        l = [(x, l[x]) for x in l]
        l.sort(key=lambda u : u[0])
        embeds, sofar, nevs, ndays, afu = [], [], 0, 0, False
        X = DailyEmbed
        def flush_embed(fu=False):
            nonlocal sofar, nevs, ndays, afu
            t, d = (title,description) if not embeds else (" ", "dummy")
            embeds.append(DailyEmbed(title, description, sofar, followup=afu))
            sofar, nevs, ndays, afu = [], 0, 0, fu
        for day, events in l:
            # invariant here : nevs < X.MAX_UNIT_EVENTS, ndays < X.MAX_DAYS
            sofar.append((day, []))
            for i, e in enumerate(events):
                sofar[-1][1].append(e)
                nevs+=1
                if nevs == X.MAX_UNIT_EVENTS:
                    more_to_go = i+1 < len(events)
                    flush_embed(more_to_go)
                    if more_to_go: sofar.append((day, []))
            ndays += 1
            if (ndays == X.MAX_DAYS):
                flush_embed(False)
        if sofar : flush_embed(False)
        # TODO: way more informative titles and descriptions (yes this todo should be with the caller)
        if not embeds : embeds = [DailyEmbed(title or "empty", description or "empty", [])]
        return embeds
    
    def _add_embed_event(self, e, start, end, day, regular, l, k=None, n=None):
        value = {
            'title': e.get('summary') or '',
            'start': start,
            'end': end,
            'color' : ':blue_square:' if regular else ':red_square:',
            'regular': regular,
            'k' : k,
            'n' : n 
        }
        if day in l : l[day].append(value)
        else: l[day]= [value]
        
    
    async def fetch_message_list_opt(self, channel_id, msg_ids):
    #TODO replace this with utils.py
        if msg_ids is None: return None
        l = [
            await self.fetch_message_opt(channel_id, msg_id)
            for msg_id in msg_ids.split(';')
        ]
        if None in l:
            await self.purge_opt_message_list(l)
            return None
        return l
    
    async def purge_opt_message_list(self, l):
        self.__log.info(f"Preparing to await deletion of {len(l)} messages.")
        for m in l:
            if m is not None:
                await m.delete()
        self.__log.info("Finished awaiting deletions of messages")
    
    def set_access(self, uid, mention, l):
      with Session(engine) as d, d.begin():
        access = d.get(DB.UserAccess, (self.__server_id, uid))
        if (l == 0):
            if access: d.delete(access)
        else:
            if access: access.access_level = l
            else: d.add(DB.UserAccess(access_level=l, thing_id=uid,
                                  mention=mention, server_id=self.__server_id))
    
    def get_access_level(self, author):
      def level(d, thing):
        r = d.get(DB.UserAccess, (self.__server_id, str(thing)))
        if r : return r.access_level
        return 0
      with Session(engine) as d:
        return max(
            max(level(d,r.id) for r in author.roles),
            level(d,author.id)
        )
    
    def list_access_levels(self):
      with Session(engine) as d, d.begin():
        r = d.scalars(select(DB.UserAccess)
                      .filter_by(server_id=self.__server_id))
        return [detached_copy(a) for a in r]
    
    async def fetch_message_opt(self, cid, mid):
        if mid is not None:
            try :
                self.__log.info(f"Preparing to await fetch_message")
                m = await self.__b.get_channel(int(cid)).fetch_message(int(mid))
                self.__log.info("Finished awaiting message.")
                return m
            except NotFound:
                self.__log.info(f"Failed with NotFound. channel={cid}, message={mid}")
        return None
    
    
    @staticmethod
    def parse_delta(s):
        env = dict()
        exec(f'ret = {s}', globals(), env)
        return env['ret'] 
    
    def safe_calendar_call(self, call):
        if self.__link is None:
            return None
        try :
            r = call()
            # if call returns no useful info, we return True to report that it succeeded
            if r is None : return True
            return r
        except CalendarApiLink.BadCredentials:
            self.__link = None
            self.connected = False
            # TODO is it helpful/necessary to nullify the token in db here?
            return None
    
    @staticmethod
    def iso_to_utcdt(d):
        d = datetime.datetime.fromisoformat(d)
        return d.replace(tzinfo=UTC)

class DailyEmbed(Embed):
    
    # To avoid counting the size of the embed case by case, we estimate a
    # large upper bound for the embed elements to know how many events we
    # can safely fit in one embed
    SINGLE_EVENT_LEN = 100 # Upper bound: size of an event line
    DAY_HEADER_LEN = 50 # Upper bound: size of daily header (just a timestamp)
    DESCRIPTION_LEN = 500 # Upper bound for embed description
    TITLE_LEN = 50 # Exact size for the title of an event
    MAX_DAYS = 25 # No more than 25 fields
    # The maximum number of single events that can appear in one embed
    MAX_UNIT_EVENTS = (6000 - DESCRIPTION_LEN - MAX_DAYS*DAY_HEADER_LEN)//SINGLE_EVENT_LEN
    
    def __init__(self, title, description, days, followup=False):
        items = [] #TODO : handle more than 25 items (pagination ?)
        for (day, events) in days:
            t = f"**<t:{int(day.timestamp())}:F>**"
            
            def line_of_event(e):
                if e['regular']:
                    return (
                        f"`{e['title']}", 
                        f"<t:{int(e['start'].timestamp())}:t> - <t:{int(e['end'].timestamp())}:t>"
                    )
                else:
                    return (
                        f" `(Day {e['k']}/{e['n']}) {e['title']}",
                        " All day"
                    )
            lines = (line_of_event(e) for e in events)
            lines = (
             (
              (
               l[:self.TITLE_LEN-3]+'...' if len(l)>self.TITLE_LEN 
                 else l+'\u00a0'*(self.TITLE_LEN-len(l))),
               t
              ) 
             for (l,t) in lines
            )
            v = '\n'.join(events[i]['color']+l+'`'+t for i,(l,t) in enumerate(lines))
            items.append(EmbedField(name=t, value=v))
        if followup and items : items[0].name = '' # The day has been announced in preceding embed
        super().__init__(title=title, description=description, fields=items)
    def __repr__(self):
        return f"Title:{self.title}\ndescription:{self.description}\nfields:{self.fields}\n"


class EventNotificationEmbed(Embed):
    
    def __init__(self, event, change_type):
        author = { # todo : better icons ? 
          'new': "\U0001f304  New event scheduled",
          'del': "\U0001f303  An event was deleted",
          'mod': "\U0001f308  An event was modified"
        }[change_type]
        title = event.get('summary') or ''
        try:
            desc = event['description']
        except KeyError:
            desc = ""
        try:
            loc = event['location']
        except KeyError:
            loc = None
        fields = []
        if loc:
            fields.append(EmbedField(
              name = 'Location',
              value = loc
            ))
        if 'dateTime' in event['start']:
            st = datetime.datetime.fromisoformat(event['start']['dateTime'][:-1])
            nd = datetime.datetime.fromisoformat(event['end']['dateTime'][:-1])
        else:
            #print("did not find dateTime field in envent", event['summary'], " start time")
            st = datetime.datetime.fromisoformat(event['start']['date'][:-1])
            nd = datetime.datetime.fromisoformat(event['end']['date'][:-1])
        fields.append(EmbedField(name='Scheduled for', value=f'<t:{int(st.timestamp())}:F>', inline=True))
        delta = str(nd-st).split('.')[0]
        fields.append(EmbedField(name='Duration:', value=delta, inline=True))
        super().__init__(title=title, description=desc, fields=fields)
        self.set_author(name=author)
