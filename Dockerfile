FROM python:3.10.12

RUN mkdir -p /usr/src/bot
WORKDIR /usr/src/bot

COPY . .

RUN pip install --no-cache-dir -r requirements.txt


CMD [ "/bin/bash", "-c", "(cd src/database && alembic upgrade head); python3 ./src/main.py" ]
