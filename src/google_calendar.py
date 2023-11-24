
from apiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from uuid import uuid4
from googleapiclient.discovery import build
import json
from googleapiclient.errors import HttpError
from  google.auth.exceptions import OAuthError, GoogleAuthError, RefreshError

from datetime import datetime, timedelta


from discord.ext import tasks #TODO : check if tasks run in parallel


GAPI_CALENDAR_SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]    

class GoogleAuthentifier:
    """ Allows to obtain login credentials for some account
    Once created, get_url() gives an url than can be passed
    to the user, then the user uses the url to authentify and
    obtain a code, then get_credentials(code) allows to obtain
    credentials than can be stored and used to start an API
    session.
    """
    
    def __init__(self):
        self.__flow = Flow.from_client_secrets_file(
            "app_secret.json", 
            scopes=GAPI_CALENDAR_SCOPES,
            redirect_uri='urn:ietf:wg:oauth:2.0:oob'
        )
        rtok = uuid4()
        self.__auth_url, state = self.__flow.authorization_url(
            prompt='consent', state=rtok
        )
        self.__valid = state==rtok
        self.__got_credentials = False
    
    def is_valid(self):
        return self.__valid
    def get_url(self):
        return self.__auth_url
    
    def get_credentials(self, code):
        if not self.__got_credentials : 
            try : 
                self.__flow.fetch_token(code=code)
            except Exception:
                return None
            self.__got_credentials = True
        return self.__flow.credentials.to_json()
    
    def get_account_info(self):
        if not self.__got_credentials:
            return None
        else:
            uinfo = build(
                'oauth2', 'v2',
                credentials = self.__flow.credentials
            )
            return uinfo.userinfo().get().execute()



class CalendarApiLink:
    
    class BadCredentials(Exception):
        """ Raised if the credentials passed to the constructor are no longer valid"""
        pass
    HttpError = HttpError
    
    @staticmethod
    def as_dict(event_list):
        return { e['id']:e for e in event_list }
            
    
    
    def __init__(self, auth_creds, watched_cals, callback):
        creds = Credentials.from_authorized_user_info(
            json.loads(auth_creds),
            scopes=GAPI_CALENDAR_SCOPES
        )
        if (not creds.valid):
            if creds.expired and creds.refresh_token:
                try: 
                    creds.refresh(Request())
                except RefreshError:
                    raise CalendarApiLink.BadCredentials("token no longer valid")
                    
            else:
                raise CalendarApiLink.BadCredentials("bad :((")
        self.__c = build('calendar', 'v3', credentials=creds)
        tmp = build('oauth2', 'v2', credentials=creds)
        uinfo = tmp.userinfo().get().execute()
        self.__email = uinfo['email']
        self.__id = uinfo['id']
        self.__pic = uinfo['picture']
        self.__watched_cals = dict()
        for cal in watched_cals:
            #print("DOING CURRENT CAL :", cal)
            self.watch_calendar(cal)
            
        self.__callback = callback

        self.update.start()
        
    def get_id(self):
        return self.__id
    def get_email(self):
        return self.__email
    
    def get_cal_name(self, cal_id):
        return self.__c.calendars().get(
            calendarId=cal_id
        ).execute()['summary']
    
    def watch_calendar(self, cal):
        if (cal in self.__watched_cals):
            return
        resp = self.__c.events().list(
                    calendarId=cal,
                    singleEvents=True,
                   ).execute()
        self.__watched_cals[cal] = {
            'events':CalendarApiLink.as_dict(resp.get('items')),
            'tok':resp.get('nextSyncToken')
        }
        
    
    def get_calendars(self):
        cals = self.__c.calendarList().list().execute().get('items')
        return [ {'id':c['id'], 
                  'name':c['summary'],
                  'timezone':c['timeZone']
                 }
                 for c in cals
               ]
    
    def get_next_events(self, calendar_id, days):
        now_dt = datetime.utcnow()
        now = now_dt.isoformat()+'Z'
        until = (now_dt+timedelta(days=days))
        res = (
            self.__c.events().list(
                calendarId=calendar_id,
                timeMin=now,
                timeMax=until,
                singleEvents=True,
                orderBy='startTime'
            ).execute().get('items')
        )
        return res
    
    def get_period_events(self, calendarId, start, end): #TODO handle timezones ?
        start = start.isoformat()+'Z'
        end = end.isoformat()+'Z'
        res = (
            self.__c.events().list(
                calendarId=calendarId,
                timeMin=start,
                timeMax=end,
                singleEvents=True,
                orderBy='startTime'
            ).execute().get('items')
        )
        return res
    
    def get_all_events(self, calendar_id):
        return self.__watched_cals[calendar_id]['events']
    
    
    @tasks.loop(seconds=5)
    async def update(self):
        modified = dict()
        for cal in self.__watched_cals:
            resp = self.__c.events().list(
                calendarId=cal,
                singleEvents=True,
                syncToken=self.__watched_cals[cal]['tok']
            ).execute() # TODO: catch expired token, do manual update
            #print("Old sync token for ", resp.get('summary'), ':  ', self.__watched_cals[cal]['tok'])
            #print("New sync token for", resp.get('summary'), ':  ', resp.get('nextSyncToken'))
            newevnts, newtok = resp.get('items'), resp.get('nextSyncToken')
            self.__watched_cals[cal]['tok'] = newtok
            evlist = self.__watched_cals[cal]['events']
            for ev in newevnts:
                if (ev['status'] == 'cancelled'):
                    evlist.pop(ev['id'], None)
                else:
                    evlist[ev['id']] = ev
            if newevnts:
                modified[cal] = newevnts
        if (self.__callback is not None):
            await self.__callback(modified)

