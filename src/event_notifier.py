
from database import db,Data

from discord.ext import tasks 
from discord import Embed, EmbedField

from google_calendar import CalendarApiLink

import datetime

from dateutil.relativedelta import relativedelta



class EventNotifier:

    def __init__(self, server_id, bot):
        self.__b = bot
        self.__server_id = server_id
        state = db.check_server_connexion(server_id)
        #print("Server Id here :\n")
        watched_cals = Data().get_all_watched_cals(server_id)
        #print("WATCHED CALS : ", watched_cals)
        cals = [c['calendar_id'] for c in watched_cals]
        print("CALS:", cals)
        self.connect(state['gtoken'], cals)
        
        
    def connect(self, tok, cals):
        if (tok):
            try:
                #print("NOW IN CONNECTING, CALS : ", cals)
                self.__link = CalendarApiLink(tok, cals, self.update)
                Data().set_server_connexion(self.__server_id, tok, self.__link.get_email())
                self.connected = True
                return self.__link.get_email()
            except CalendarApiLink.BadCredentials:
                self.__link = None
        else:
            self.__link = None
        self.connected = self.__link is not None
    
    
    def add_watch(self, channel_id, cal_id, new, dele, mod, name):
        new_col = {
            'server_id': self.__server_id,
            'watch_id': name,
            'channel_id' : channel_id,
            'filter' : '',
            'updates_new': new,
            'updates_mod': mod,
            'updates_del': dele,
            'replace':'',
            'calendar_id': cal_id,
            'calendar_name':'',
        }
        db.insert_cols_in_table('watched_calendar', [new_col])
        self.__link.watch_calendar(cal_id)
        
    
    def get_all_watched_cals(self):
        return Data().get_all_watched_cals(self.__server_id)        
        
    
    def update(self, modifs):
        for cal in modifs:
            for watched in Data().get_all_watched_cals_for_cal(self.__server_id, cal):
                #TODO: delete old messages
                for e in modifs[cal]:
                    if not True : #TODO self.filter_tags(e['tags'], watched['filter']):
                        continue
                        
                    #TODO : modifier les récaps
                    
                    body = None
                    if e['status'] == 'cancelled' :
                        if watched['updates_del']:
                            # TODO : remember this message
                            body = 'Deleted event : \n'+self.string_of_event(e)
                    elif e['updated'] == e['created']:
                        if watched['updates_new']:
                            body = 'New event : \n'+self.string_of_event(e)
                    else: # Event modified
                        if watched['updates_mod']:
                            body = 'Updated event : \n'+self.string_of_event(e)
                    if body:
                        #print("WATCHED:", watched['channel_id'])
                        u = self.__b.get_channel(int(watched['channel_id'])).send(body) #channel_id
                        t = self.__b.loop.create_task(u)
    
    def get_all_calendars(self):
        return self.__link.get_calendars()          
    
    def get_all_watches(self):
        return Data().get_all_watched_cals(self.__server_id)      
    
    
    def check_summary_uniqueness(self, new_name):
        return Data().get_summary(self.__server_id, new_name) is None
    def check_watch_uniqueness(self, new_name):
        return Data().get_watch(self.__server_id, new_name) is None
    
    async def add_summary(self, watch_cal, duration, in_months, base_day, header, name):
        base_day_repr = base_day.isoformat()
        duration = relativedelta(months=duration) if in_months else relativedelta(days=duration)
        #TODO print the message
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
        embed = self.make_daily_embed(new_col['summary_id'], "", events)
        watch = Data().get_watch(self.__server_id, new_col['watch_id'])
        u = await self.__b.get_channel(int(watch['channel_id'])).send(new_col['header'], embed=embed)
        new_col['message_id'] = str(u.id)
        Data().insert_cols_in_table('event_summary', [new_col])
        #self.__b.loop.create_task(u)
        
    
    # TODO TODO
    def string_of_event(self, event) :
        return "Body placeholder"
    def filter_tags(self, tags, filt):
        return True 
    
    def get_summary_events(self, summary): #TODO update_summary_dates
        base_date = datetime.datetime.fromisoformat(summary['base_date'])
        locs=dict()
        exec(f'duration = {summary["frequency"]}', globals(), locs)
        end_date = base_date+locs['duration']
        watch = Data().get_watch(summary['server_id'], summary['watch_id'])
        events = self.__link.get_period_events(watch['calendar_id'], base_date, end_date)
        return events
    
    def make_daily_embed(self, title, description, events):
        l = []
        for e in events: # TODO : Handle(or just ignore) multi-day events
            day = datetime.datetime.fromisoformat(e['start']['dateTime']).date().isoformat()
            start = datetime.datetime.fromisoformat(e['start']['dateTime'])
            end = datetime.datetime.fromisoformat(e['end']['dateTime'])
            value = {
                'title': e['summary'],
                'start': start,
                'end': end,
                'color': '008000' #TODO correct handling of colors, color endpoint in the cal api
            }
            if not l or  day > l[-1][0]:
                l.append((day, []))
            l[-1][1].append(value)
        return DailyEmbed(title, description, l)
            

class DailyEmbed(Embed):
    
    def __init__(self, title, description, days):
        items = [] #TODO : handle more than 25 items (pagination ?)
        for (day, events) in days:
            t = f"**{day}**"
            v = '\n'.join( #TODO handle long titles and pad short titles, have internal representation of events(not dicts)
              f":blue_square: `{e['title']}` <t:{int(e['start'].timestamp())}:t> <t:{int(e['end'].timestamp())}:t>"
              for e in events
            )
            items.append(EmbedField(name=t, value=v))
        super().__init__(title=title, description=description, fields=items)
        
