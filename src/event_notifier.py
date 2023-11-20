
from database import db,Data

from discord.ext import tasks 

from google_calendar import CalendarApiLink

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
    
    
    def add_watch(self, channel_id, cal_id, new, dele, mod):
        unique_id = db.find_next_watch_id(self.__server_id)
        new_col = {
            'server_id': self.__server_id,
            'watch_id': unique_id,
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
                        self.__b.loop.create_task(u)
    
    def get_all_calendars(self):
        return self.__link.get_calendars()          
    
    def get_all_watches(self):
        return Data().get_all_watched_cals(self.__server_id)      
    
    
    def check_summary_uniqueness(self, new_name):
        return Data().get_summary(self.__server_id, new_name) is None
    
    def add_summary(self, watch_cal, duration, in_months, base_day, name):
        base_day_repr = base_day.isoformat()
        duration = relativedelta(months=duration) if in_months else relativedelta(days=duration)
        #TODO print the message
        new_col = {
            'server_id': self.__server_id,
            'watch_id' :watch_cal['watch_id'],
            'summary_id':name,
            'base_date': base_day_repr,
            'frequency': repr(duration),
            'header': "TODO : HEADER",
            'message_id' : None
        }
        Data().insert_cols_in_table('event_summary', [new_col])
    
    # TODO TODO
    def string_of_event(self, event) :
        return "Body placeholder"
    def filter_tags(self, tags, filt):
        return True              
