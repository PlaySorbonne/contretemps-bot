
from database import Data

from discord.ext import tasks 
from discord import Embed, EmbedField
from discord.errors import NotFound

from google_calendar import CalendarApiLink

import datetime

from dateutil.relativedelta import relativedelta
from dateutil.utils import within_delta



class EventNotifier:

    def __init__(self, server_id, server_name, bot):
        self.__b = bot
        self.__server_id = server_id
        self.__name = server_name
        state = Data().check_server_connexion(server_id)
        self.connect(state['gtoken'])
        self.check_summaries.start()
        print("Succesfully configured", self.__name)
        
        
    def connect(self, tok):
        watched_cals = Data().get_all_watched_cals(self.__server_id)
        cals = [c['calendar_id'] for c in watched_cals]
        #print("CALS:", cals)
        if (tok):
            try:
                self.__link = CalendarApiLink(tok, cals, self.update)
                Data().set_server_connexion(self.__server_id, tok, self.__link.get_email())
                # TODO : check for email (account) change, which would dismiss all old watched_calendars
                self.connected = True
                return self.__link.get_email()
            except CalendarApiLink.BadCredentials:
                self.__link = None
                # TODO : put NULL as tok in the db
        else:
            self.__link = None
        self.connected = self.__link is not None
    
    async def add_watch(self, channel_id, cal, new, dele, mod, name):
        new_col = {
            'server_id': self.__server_id,
            'watch_id': name,
            'channel_id' : channel_id,
            'filter' : '',
            'updates_new': new,
            'updates_mod': mod,
            'updates_del': dele,
            'replace':'',
            'calendar_id': cal['id'],
            'calendar_name':cal['name'],
        }
        Data().insert_cols_in_table('watched_calendar', [new_col])
        r = self.safe_calendar_call(
            lambda : self.__link.watch_calendar(cal['id'])
        )
        if not r:
            await self.__b.get_channel(int(channel_id)).send(
              "Warning : I am disconnected from the Google Account",
              delete_after=60
            )
        
    
    def get_all_watched_cals(self):
        return Data().get_all_watched_cals(self.__server_id)        
        
    
    async def update(self, modifs):
        if (self.__link is None):
            return
        #TODO handle timezones ?
        d = Data()
        for cal in modifs:
            for watched in d.get_all_watched_cals_for_cal(self.__server_id, cal):
                for e in modifs[cal]:
                    if not True : #TODO self.filter_tags(e['tags'], watched['filter']):
                        continue

                    
                    change = None
                    if e['status'] == 'cancelled' :
                        if watched['updates_del']:
                            change = 'del'
                    elif within_delta(
                        datetime.datetime.fromisoformat(e['updated'][:-1]),
                        datetime.datetime.fromisoformat(e['created'][:-1]),
                        datetime.timedelta(seconds=2)
                         ):
                        if watched['updates_new']:
                            change = 'new'
                    else: # Event modified
                        if watched['updates_mod']:
                            change = 'mod'
                    if change:
                        u = await self.__b.get_channel(int(watched['channel_id'])).send(
                          "",
                          embed=EventNotificationEmbed(e, change)
                        )
                        # TODO : store this message and delete it when new update / when the watch is deleted
                # Handling all the summaries attached to the watch
                summaries = d.get_watch_summaries(self.__server_id, watched['watch_id'])
                for s in summaries:
                    await self.update_summary_message(s, watch=watched, d=d)

    
    @tasks.loop(seconds=5)
    async def check_summaries(self):
        if (self.__link is None):
            return #TODO : maybe message the admins at least one time ?
        d = Data()
        for w in d.get_all_watched_cals(self.__server_id):
            for s in d.get_watch_summaries(self.__server_id, w['watch_id']):
                # check if it is time to update the summary base date
                base_date = datetime.datetime.fromisoformat(s['base_date'])
                delta = EventNotifier.parse_delta(s['frequency'])
                now = datetime.datetime.now()
                if (now > base_date+delta): 
                    print("Found finished summary")
                    while (now > base_date+delta):
                        base_date += delta
                    d.modify_summary(s, {'base_date':base_date.isoformat()})
                    s = d.get_summary(self.__server_id, s['watch_id'], s['summary_id'])
                    await self.delete_summary_message(s, d=d)
                    await self.publish_summary(s, d=d)
                    
    
    async def delete_watch(self, watch_id):
        d = Data()
        w = d.get_watch(self.__server_id, watch_id)
        if w is None:
            return False
        S = d.get_watch_summaries(self.__server_id, watch_id)
        for s in S:
            await self.delete_summary(watch_id, s['summary_id'], d=d) # redundant requests :[[
        d.delete_watch(self.__server_id, watch_id)
        return True
    
    async def delete_summary(self, watch_id, summary_id, d=None):
        if d is None: d=Data()
        s = d.get_summary(self.__server_id, watch_id, summary_id)
        w = d.get_watch(self.__server_id, watch_id)
        if s is None: #TODO proper logging
            print(f"Did not find summary {summary_id}")
            return False
        await self.delete_summary_message(s, watch=w, upd_db=False, d=d)
        d.delete_summary(self.__server_id, watch_id, summary_id)
        return True
    
    async def clear_summaries(self, watch_id, d=None):
        if d is None: d=Data()
        for s in d.get_watch_summaries(self.__server_id, watch_id):
            await self.delete_summary(s['watch_id'], s['summary_id'], d) #redundant db requests :[
    
    async def delete_summary_message(self, summary, watch=None, upd_db=False, d=None):
        if d is None: d=Data()
        if watch is None:
            watch = d.get_watch(self.__server_id, summary['watch_id'])
        if summary['message_id'] is not None:
             try:
                m = await self.__b.get_channel(int(watch['channel_id'])).fetch_message(int(summary['message_id']))
                if (m.author == self.__b.user): #should be always true but extra check since we're deleting a message
                    await m.delete()
             except NotFound: #message does not exist anymore, nothing to do
                print("Tried to delete message from server, but it did not exist :((((")
        if (upd_db):
            d.modify_summary_message(summary, None)
    
    async def update_summary_message(self, summary, watch=None, d=None):
        if watch is None:
            watch = d.get_watch(self.__server_id, summary['watch_id'])
        if d is None : d = Data()
        
        new_evs = self.get_summary_events(summary)
        if (new_evs is None):
            await self.__b.get_channel(int(watch['channel_id'])).send(
              f'Warning : I am diconnected from Google, summary {summary["summary_id"]} not updated'
            )
            return
        new_embd = self.make_daily_embed("", "", new_evs)
        m = await self.fetch_message_opt(watch['channel_id'], summary['message_id'])
        await self.publish_summary(summary, m=m, d=d)


    async def publish_summary(self, summary, m=None, watch=None , d=None):
        if d is None: d=Data()
        if watch is None:
            watch = d.get_watch(self.__server_id, summary['watch_id'])
        new_evs = self.get_summary_events(summary)
        if (new_evs is None):
            await self.__b.get_channel(int(watch['channel_id'])).send(
              f'Warning : I am diconnected from Google, summary {summary["summary_id"]} cannot be published'
            )
            return
        content = '# ' + summary['summary_id'] + '\n' + summary['header']
        new_embd = self.make_daily_embed("", "", new_evs)
        if m is None :
            m = await self.__b.get_channel(int(watch['channel_id'])).send(content=content, embeds=new_embd)
            d.modify_summary(summary, {'message_id' : str(m.id) })
        else:
            await m.edit(content=content, embeds=new_embd)
        
    
    def get_all_calendars(self):
        """
        Returns all the calendars that are currently watched in the server
        If the google connexion is no longer valid, returns None
        """
        return self.safe_calendar_call(lambda:self.__link.get_calendars())          
    
    def get_all_watches(self):
        res = Data().get_all_watched_cals(self.__server_id)
        return res if res is not None else []
        
    def get_all_summaries(self, watch_id):
        res = Data().get_watch_summaries(self.__server_id, watch_id)
        return res if res is not None else []
    
    
    def check_summary_uniqueness(self, watch_id, new_name):
        return Data().get_summary(self.__server_id, watch_id, new_name) is None
    def check_watch_uniqueness(self, new_name):
        return Data().get_watch(self.__server_id, new_name) is None
    
    async def add_summary(self, watch_cal, duration, in_months, base_day, header, name):
        base_day_repr = base_day.isoformat()
        duration = relativedelta(months=duration) if in_months else relativedelta(days=duration)
        new_col = {
            'server_id': self.__server_id,
            'watch_id' :watch_cal['watch_id'],
            'summary_id':name,
            'base_date': base_day_repr,
            'frequency': repr(duration),
            'header': header,
            'message_id' : None
        }
        events = self.get_summary_events(new_col)
        if (events is None):
            await self.__b.get_channel(int(watch_cal['channel_id'])).send(
              f'Warning : I am diconnected from Google, summary {name} not published'
            )
            # We remember the summary for future publication
            Data().insert_cols_in_table('event_summary', [new_col])
            return
        Data().insert_cols_in_table('event_summary', [new_col])
        await self.publish_summary(new_col)
        
    
    def get_watches_names(self):
        W = Data().get_all_watched_cals(self.__server_id)
        return [w['watch_id'] for w in W]
    
    def get_summaries_names(self, watch_id):
        S = Data().get_watch_summaries(self.__server_id, watch_id)
        return [s['summary_id'] for s in S]
    
    # TODO TODO
    def filter_tags(self, tags, filt):
        return True 
    
    def get_summary_events(self, summary):
        """
        Returns a list of the next events for a summary
        If the connexion to the calendar is no longer valid, returns None
        """
        base_date = datetime.datetime.fromisoformat(summary['base_date'])
        locs=dict()
        exec(f'duration = {summary["frequency"]}', globals(), locs)
        end_date = base_date+locs['duration']
        watch = Data().get_watch(summary['server_id'], summary['watch_id'])
        events = self.safe_calendar_call(
            lambda : self.__link.get_period_events(watch['calendar_id'], base_date, end_date)
        )
        return events
    
    def make_daily_embed(self, title, description, events):
        l, mday_l = [],[]
        for e in events: # TODO : Handle(or just ignore) multi-day events
            regular = 'dateTime' in e['start']
            date_field = 'dateTime' if regular else 'date'
            day = datetime.datetime.fromisoformat(e['start'][date_field]).date().isoformat()
            start = datetime.datetime.fromisoformat(e['start'][date_field])
            end = datetime.datetime.fromisoformat(e['end'][date_field])
            value = {
                'title': e['summary'],
                'start': start,
                'end': end,
            }
            if regular:
                if not l or  day > l[-1][0]:
                    l.append((day, []))
                l[-1][1].append(value)
            else :
                mday_l.append(value)
        reg_embed = DailyEmbed(title, description, l)
        if mday_l:
            multi_embed = MultiDayEmbed("Events that happen across multiple days", mday_l)
            return [multi_embed, reg_embed]
        return [reg_embed]
    
    
    def set_access(self, uid, mention, l):
        if (l == 0):
            Data().delete_access(self.__server_id, str(uid))
        else:
            Data().set_access(self.__server_id, str(uid), mention, l)
    
    def get_access_level(self, author):
        return max(
            max(Data().get_access(self.__server_id, str(r.id)) for r in author.roles),   
            Data().get_access(self.__server_id, str(author.id))
        )
    
    def list_access_levels(self):
        return Data().get_access_levels(self.__server_id)
    
    async def fetch_message_opt(self, cid, mid):
        if mid is not None:
            try :
                return await self.__b.get_channel(int(cid)).fetch_message(int(mid))
            except NotFound:
                return None
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

class DailyEmbed(Embed):
    
    def __init__(self, title, description, days):
        items = [] #TODO : handle more than 25 items (pagination ?)
        for (day, events) in days:
            t = f"**<t:{int(datetime.datetime.fromisoformat(day).timestamp())}:F>**"
            
            lines = (
              (
                f"`{e['title']}",
                f" <t:{int(e['start'].timestamp())}:t> - <t:{int(e['end'].timestamp())}:t>"
              )
              for e in events
            )
            lines = ( ((l[:47]+'...' if len(l)>50 else l+'\u00a0'*(50-len(l))),t) for (l,t) in lines)
            v = '\n'.join(':blue_square:'+l+'`'+t for (l,t) in lines)
            items.append(EmbedField(name=t, value=v))
        super().__init__(title=title, description=description, fields=items)

class MultiDayEmbed(Embed):
    
    def __init__(self, title, events):
        wdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                 'Friday', 'Saturday', 'Sunday' ]
        desc = ""
        for e in events:
            sday = e['start']
            eday = e['end']
            sdow = wdays[sday.weekday()]
            edow = wdays[eday.weekday()]
            
            sfrmt = f'{sdow} <t:{int(sday.timestamp())}:D>'
            efrmt = f'{edow} <t:{int(eday.timestamp())}:D>'
            
            desc += f":green_square: {e['title']}\n"
            desc += 10*'\u00a0' + f'**Start time**: {sfrmt}\n'
            desc += 10*'\u00a0' + f'**End time**: {efrmt}\n'
        super().__init__(title=title, description=desc)

class EventNotificationEmbed(Embed):
    
    def __init__(self, event, change_type):
        author = { # todo : better icons ? 
          'new': "\U0001f304  New event scheduled",
          'del': "\U0001f303  An event was deleted",
          'mod': "\U0001f308  An event was modified"
        }[change_type]
        title = event['summary']
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
            st = datetime.datetime.fromisoformat(event['start']['dateTime'])
            nd = datetime.datetime.fromisoformat(event['end']['dateTime'])
        else:
            #print("did not find dateTime field in envent", event['summary'], " start time")
            st = datetime.datetime.fromisoformat(event['start']['date'])
            nd = datetime.datetime.fromisoformat(event['end']['date'])
        fields.append(EmbedField(name='Scheduled for', value=f'<t:{int(st.timestamp())}:F>', inline=True))
        delta = str(nd-st).split('.')[0]
        fields.append(EmbedField(name='Duration:', value=delta, inline=True))
        super().__init__(title=title, description=desc, fields=fields)
        self.set_author(name=author)
        
                
            
