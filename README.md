# ContretempsBot
This is a Discord bot allowing to sync a Google calendar with a Discord server. The end-goal is to make a complete clone of the [Chronicle Bot](https://chroniclebot.com/) that implements all of its functionalities.


## Usage

There are only two supported functionalities for now : Event Notifiers, and Event Summaries. All the interactions with the bot are done using slash commands.

After adding the bot to a server, the fist thing to do is to associate it to a Google account in order to access its calendars.
For that, use the `/connect` command, which gives a link allowing to authenticate with an account.

### Event Notifiers
An event notifier allows to associate a calendar with a Discord text channel. The bot then sends a message to the channel each time there is a change in the calendar (a new event, a canceled event, or a modified event). One can configure an event notifier using the command `/add_new_event_notifier`.
### Event Summaries
Given an Event Notifier, one can have the bot to regularly send a summary of all the events in the calendar over a specified period (for example, sending the summary of the events for the week each Monday morning). This aims to replicate [this functionality in the Chronicle Bot](https://chroniclebot.com/docs/notifier/event-summaries).
One can configure a summary using the `/make_summary` command. 
### Access
When the bot joins the server, only the server owner can use the commands. One can allow other users or roles the right to use the commands with the command `/set_access`. There are three access levels: 0 is the default one, 1 allows to create and edit summaries and notifiers, and 2 allows to also edit the access levels of other users. The command `/list_access` allows to view the current access levels.

## Hosting
Here are the steps to run the bot :

The required packages are python3, pip, and sqlite3



1. Clone this repository - `git clone https://github.com/PlaySorbonne/contretemps-bot.git`
2. Create a Discord application through [Discord's developer portal](https://discord.com/developers/applications) and set an OAuth2 token. Copy the token and put it in the base folder in a file named .discord_token - `echo -n [your token] > .discord_token`
3. Create a new project in [Google Cloud Services](https://cloud.google.com), and [create OAuth 2 credentials](https://cloud.google.com/docs/authentication?authuser=2&hl=fr) with at least '/auth/calendar' and '/auth/userinfo.email' as scopes. Download the OAuth credentials file and put it in the base folder under the name 'app_secret.json'
4. Initialize the database file in the base directory under the name 'data.db' - `sqlite3 ./data.db < ./src/db_schema.sql`
5. Install all dependencies in the requirements.txt file - `python3 -m pip install -r requirements.txt`
6. Run the bot : `python3 src/bot.py`

The invite link to add the bot (containing the correct scopes and permissions) is:
https://discord.com/api/oauth2/authorize?client_id=[YOUR_DISCORD_APP_ID]&permissions=17875654069312&scope=applications.commands%20bot
where you replace [YOUR_DISCORD_APP_ID] with the id that can be found when creating the app in step 2.




## Development

### Tools and libraries

The bot is written in python, and uses: 

-  **[Pycord](https://docs.pycord.dev/en/stable/)** as an API wrapper for Discord, chosen mainly for its support of [Application Commands](https://discord.com/developers/docs/interactions/application-commands).
    - General Discord API documentation can be found [here](https://discord.com/developers/docs/intro)
    - An introductory guide to Pycord, including its interface for Application Commands and Components can be found [here](https://guide.pycord.dev/getting-started/more-features)
-  **Google's [Calendar API](https://developers.google.com/calendar/api/quickstart/python)** using Google's python library for working with the API
-  Pycord's [tasks extension](https://guide.pycord.dev/extensions/tasks) to run periodic tasks


### Code structure
All the relevant files are in the [src/](src/) folder. There are three main components :

1. [bot.py](src/bot.py) : the entry-point, the bot client is created here, and all the Slash Commands and their corresponding forms are defined here.
2. [event_notifier.py](src/event_notifier.py) : here is defined the EventNotifier class, which is the internal representation of a single server. In [bot.py](src/bot.py), an EventNotifier instance is created for each server where the bot is a member. All the logic regarding the behavior of each feature is enclosed in this class.
3. [google_calendar.py](src/google_calendar.py) : here are defined the GoogleAuthentifier and CalendarApiLink. The first one is used in [bot.py](src/bot.py) inside the `/connect` command in order to authenticate. The second one is instantiated with credentials and encloses all the needed API calls to Google Calendar, it is used by instances of the EventNotifier class.

In addition, there is a small database storing the credentials for the Google account, and all the configured event notifiers and event summaries. The schema is in [src/db_schema.sql](src/db_schema.sql).
Access to the database is done through an instance of the Data class in [database.py](src/database.py) which encloses used SQL requests. It is used by instances of the EventNotifier class. (PS: an event notifier is named 'watched_calendar' in the database and in bot.py because i am bad at naming things consistently)


### TODO
#### Fixes/Adjustments in the already implemented things to make it usable
- [x] Add a permission system, with specifying the roles allowed to configure notifiers and summaries.
- [ ] Add commands to visualize current notifiers and summaries, and to modify/delete one.
    - [x] Visualize
    - [x] Delete
    - [ ] Modify
- [x] Handle token expiration for the google calendar API. It is only handle on first connection for now. It needs to be checked in the `update()` method of CalendarApiLink, which needs to hold an attribute it sets when the token expires. It also needs to be checked in every EventNotifier method that makes API calls through CalendarApiLink, and it needs to put itself in a disconnected state if the token expires.
- [x] Handle daily events everywhere (in summaries, show them in a different embed ? )
- [x] Some agendas currently give delayed updates (they do not give all the events with the first API request). This can cause a message spam from the bot when a notifier is set, and also infinite messages with reccuring events. This is because of the max number of events in a single response, we need to check nextPageToken each time, and limit lookup period (1 year seems reasonable)
- [ ] When there is a re-connection attempt after a disconnection, check if it is the same google account, otherwise ask the user if we should delete all the old notifiers and summaries
- [x] Handle the case where there are more than 25 channels to choose from. In the form presented to the user when creating an event notifier (called **AddWatchForm**), we use a [Select Menu](https://guide.pycord.dev/interactions/ui-components/dropdowns) to allow the user to choose the channel associated to the notifier. But the API only allows for 25 elements in a Select Menu. So we should handle the case where there are more than 25 choices (selecting a channel, selecting a calendar, and selecting a notifier when creating a summary) by splitting the choice list into parts of 23 elements, then adding a 'Prec' and 'Next' options. 
    - [x] Channel choice in Event Notifier creation
    - [x] Calendar choice in Event Notifier creation
    - [x] Notifier choice in Event Summary creation
- [ ] Check date sanity when allowing the user to create an event summary (only allow future dates). This is to be done in the **MakeSummaryForm** class.
- [ ] Make a command the force an update to all the summaries in the server (can be useful for example if there have been modified events while the bot is down)
- [ ] Handle the case where a summary has more than 25 days to account for. Since an Embed can only have 25 Items, something must be done about this. Chronicle Bot's solution is to split the summary into multiple messages
- [ ] Remember notification messages sent by the notifier and delete them if a new one is sent to avoid spam (and make this an option in the notifier creation form)


#### Structural changes in code
- [ ] Find a better structure for bot.py and organize in a more readable way
- [ ] Add logging everywhere
- [ ] Handle language/translation (at least fr and en)
#### Remaining features to implement
- [ ] Add an option in the summary creation to choose between a brief summary (show only the event's name and time) or in detail (also show event's description and time).
- [ ] (idea, not in Chronicle Bot) Show a distinct id for each event in the summary, and allow any user to use a command (like `/details_about_event` or something) to see the details.
- [ ] Add an option to specify filters in the event notifier, which takes into account only the events of the calendar that have a title or a description that satisfies the filter (I don't know how much this can be useful, but it's a feature in Chronicle Bot)
- [ ] **Sync discord events with calendar events** This is the main missing feature for now. [Here is how it should behave](https://chroniclebot.com/docs/notifier/discord-event-sync)
- [ ] **Reminders** The ability to make the bot send a reminder message a specified time before each event. [Here is how it should behave](https://chroniclebot.com/docs/notifier/scheduled-reminders)