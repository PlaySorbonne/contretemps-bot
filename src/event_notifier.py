
from database import db

from discord.ext import tasks 

from google_calendar import CalendarApiLink



class EventNotifier:

    def __init__(self, server_id, bot):
        self.__b = bot
        self.__server_id = server_id
        state = db.check_server_connexion(server_id)
        self.connect(state['gtoken'])
        
        
    def connect(self, tok):
        if (tok):
            try:
                self.__link = CalendarApiLink(tok, [], self.update)
            except CalendarApiLink.BadCredentials:
                self.__link = None
        else:
            self.__link = None
        self.connected = self.__link is not None
    
    
    def update(self, modifs):
        for cal in modifs:
            for watched in get_all_watched_cals_for_cal(self, self.__server_id, cal):
                #TODO: delete old messages
                for e in modifs[cal]:
                    if not self.filter_tags(e['tags'], watched['filter']):
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
                        self.__b.get_channel(watched['channel_id']).send(body)
    
    def get_all_calendars(self):
        return self.__link.get_calendars()                
    
    
    # TODO TODO
    def string_of_event(self, event) :
        return "Body placeholder"
    def filter_tags(self, tags, filt):
        return True              
