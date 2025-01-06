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
from inspect import iscoroutinefunction


from discord.ext import tasks


GAPI_CALENDAR_SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid'
]

MAX_AHEAD_LOOKUP = timedelta(days=366)

class GoogleAuthentifier:
    """ 
    Allows to obtain login credentials for some account
    
    Once created, o.get_url() gives an url than can be passed
    to the user, then the user uses the url to authentify and
    obtain a code, then o.get_credentials(code) allows to obtain
    credentials than can be stored and used to start an API
    session.
    
    Once the credentials are obtained, o.get_account_info() 
    allows to get the email of the connected account.
    """
    
    def __init__(self):
        self.__flow = Flow.from_client_secrets_file(
            "data/app_secret.json",
            scopes=GAPI_CALENDAR_SCOPES,
            redirect_uri='https://127.0.0.1/'
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
            
    def might_refresh_error(pass_as=None, msg=""):
        """
        Decorator for handling an unexpected token expiration/revocation
        """
        def dec(f):
            if not iscoroutinefunction(f):
                def new_f(*args, **kwargs):
                    if (not args[0].__valid):
                        if pass_as:
                            raise pass_as(msg)
                        else:
                            return
                    try:
                        return f(*args, **kwargs)
                    except RefreshError:
                        args[0].__valid = False
                        args[0].update.stop()
                        if (pass_as):
                            raise pass_as(msg)
            else: # this is a quite ugly copy-paste :[[
                async def new_f(*args, **kwargs): 
                    if (not args[0].__valid):
                        if pass_as:
                            raise pass_as(msg)
                        else:
                            return
                    try:
                        return await f(*args, **kwargs)
                    except RefreshError:
                        args[0].__valid = False
                        args[0].update.stop()
                        if (pass_as):
                            raise pass_as(msg)
            return new_f
        return dec
    
    
    def __init__(self, auth_creds, watched_cals, callback):
        creds = Credentials.from_authorized_user_info(
            json.loads(auth_creds),
            scopes=GAPI_CALENDAR_SCOPES
        )
        if creds.refresh_token:
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
        self.__valid = True
        self.__watched_cals = dict()
        for cal in watched_cals:
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
        before = datetime.now()+MAX_AHEAD_LOOKUP
        resp = self.__c.events().list(
                    calendarId=cal,
                    timeMax=before.isoformat()+'Z',
                    singleEvents=True,
                    timeZone="Etc/UTC"
                   ).execute()
        while 'nextPageToken' in resp:
            resp = self.__c.events().list(
                pageToken = resp['nextPageToken'],
                calendarId = cal,
                timeZone="Etc/UTC",
                singleEvents=True
            ).execute()
        self.__watched_cals[cal] = {
            'events':CalendarApiLink.as_dict(resp.get('items')),
            'tok':resp.get('nextSyncToken')
        }
        return True
        
    
    @might_refresh_error(BadCredentials)
    def get_calendars(self):
        cals = self.__c.calendarList().list().execute().get('items')
        return [ {'id':c['id'], 
                  'name':c['summary'],
                  'timezone':c['timeZone']
                 }
                 for c in cals
               ]
    
    @might_refresh_error(BadCredentials)
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
                orderBy='startTime',
                timeZone="Etc/UTC"
            ).execute().get('items')
        )
        return res
    
    @might_refresh_error(BadCredentials)
    def get_period_events(self, calendarId, start, end): 
        start = start.isoformat().split('+')[0]+'Z'
        end = end.isoformat().split('+')[0]+'Z'
        res = (
            self.__c.events().list(
                calendarId=calendarId,
                timeMin=start,
                timeMax=end,
                singleEvents=True,
                orderBy='startTime',
                timeZone="Etc/UTC"
            ).execute().get('items')
        )
        return res
    
    @might_refresh_error(BadCredentials)
    def get_all_events(self, calendar_id):
        return self.__watched_cals[calendar_id]['events']
    
    
    @tasks.loop(seconds=5)
    @might_refresh_error()
    async def update(self):
        modified = dict()
        for cal in self.__watched_cals:
            args = {
              'calendarId':cal,
              'singleEvents':True,
              'syncToken':self.__watched_cals[cal]['tok'],
              'showDeleted':True,
              'timeZone' : "Etc/UTC"
            }
            try:
                resp = self.__c.events().list(**args).execute()
            except HttpError:
                print(f"[CalendarApiLink] syncToken expired on {datetime.utcnow()} for calendar {cal}")
                args.pop('syncToken')
                resp = self.__c.events().list(**args).execute()
            newevnts = resp.get('items')
            while 'nextPageToken' in resp:
                resp = self.__c.events().list(
                    calendarId = cal,
                    singleEvents = True, 
                    showDeleted = True,
                    pageToken = resp['nextPageToken'],
                    timeZone = "Etc/UTC"
                ).execute()
                newevnts += resp.get('items')
            self.__watched_cals[cal]['tok'] = resp['nextSyncToken']
            evlist = self.__watched_cals[cal]['events']
            for ev in newevnts:
                if (ev['status'] == 'cancelled'):
                    evlist.pop(ev['id'], None)
                else:
                    evlist[ev['id']] = ev
            if newevnts:
                modified[cal] = newevnts
        updates_numbeer = sum(sum(cal) for cal in modified.values())
        if sum(sum(cal) for cal in modified.values()) > 10:
          print(f"[CalendarApiLink] Too many updated events ({updates_numbeer})")
          return
        if (self.__callback is not None):
            await self.__callback(modified)

