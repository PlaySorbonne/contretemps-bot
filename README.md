#ContretempsBot
This is a Discord bot allowing to sync a Google calendar with a Discrd server. The endgoad is to make a complete clone of the [Chronicle Bot](https://chroniclebot.com/) that implements all of its functionalities.


## Usage

There are only two supported functionalities for now : Event Notifiers, and Event Summaries. All the interactions with the bot are done using slash commands.

After adding the bot to a server, the fist thing to do is to associate it to a Google account in order to access its calendars.
For that, use the `/connect` command, which gives a link allowing to authenticate with an account.

### Event Notifiers
An event notifier allows to associate a calendar with a Discord text channel. The bot then sends a message to the channel each time there is a change in the calendar (a new event, a canceled event, or a modified event). One can configure an event notifier using the command `/add_new_event_notifier`.
### Event Summaries
Given an Event Notifier, one can have the bot to regularly send a summary of all the events in the calendar over a specified period (for example, sending the summary of the events for the week each monday morning). This aims to replicate [this functionality in the Chronicle Bot](https://chroniclebot.com/docs/notifier/event-summaries).
One can configure a summary using the `/make_summary` command. 


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
