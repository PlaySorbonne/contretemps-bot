FROM python:3.10
FROM gorialis/discord.py

RUN mkdir -p /usr/src/bot
WORKDIR /usr/src/bot

COPY . .

RUN pip install --no-cache-dir -r requirements.txt

CMD [ "python3", "discord_bot.py" ]
