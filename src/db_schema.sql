-- This file is part of ContretempsBot <https://github.com/PlaySorbonne/contretemps-bot>
-- Copyright (C) 2023-present PLAY SORBONNE UNIVERSITE
-- Copyright (C) 2023 DaBlumer
--
-- This program is free software: you can redistribute it and/or modify
-- it under the terms of the GNU General Public License as published by
-- the Free Software Foundation, either version 3 of the License, or
-- (at your option) any later version.
--
-- This program is distributed in the hope that it will be useful,
-- but WITHOUT ANY WARRANTY; without even the implied warranty of
-- MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
-- GNU General Public License for more details.
--
-- You should have received a copy of the GNU General Public License
-- along with this program.  If not, see <http://www.gnu.org/licenses/>.


CREATE TABLE server_connexion (
    server_id CHAR(20) PRIMARY KEY,
    gtoken char(1000) NULL,
    gmail varchar(100) NULL
);


CREATE TABLE user_access (
    server_id CHAR(20),
    thing_id CHAR(20),
    mention VARCHAR(20),
    access_level INTEGER,
    FOREIGN KEY(server_id) REFERENCES server_connexion(server_id),
    PRIMARY KEY (server_id, thing_id)
);


CREATE TABLE watched_calendar (
    server_id CHAR(20),
    watch_id VARCHAR(20),
    channel_id CHAR(20),
    filter VARCHAR(20),
    updates_new INTEGER,
    updates_mod INTEGER,
    updates_del INTEGER,
    replace CHAR(10),
    calendar_id VARCHAR(50),
    calendar_name VARCHAR(50),
    FOREIGN KEY(server_id) REFERENCES server_connexion(server_id),
    PRIMARY KEY (server_id, watch_id)
);

CREATE TABLE message (
    server_id CHAR(20),
    message_id CHAR(20),
    watch_id VARCHAR(30),
    type CHAR(20),
    subtype CHAR(20),
    FOREIGN KEY(server_id,watch_id) REFERENCES watched_calendar(server_id, watch_id),
    PRIMARY KEY(message_id)
);

CREATE TABLE event_summary(
    server_id CHAR(20),
    watch_id CHAR(20),
    summary_id VARCHAR(20),
    base_date VARCHAR(20),
    frequency VARCHAR(20), 
    header VARCHAR(100), 
    message_id CHAR(20), 
    FOREIGN KEY(server_id, watch_id) REFERENCES watched_calendar(server_id, watch_id),
    FOREIGN KEY(message_id) REFERENCES message(message_id),
    PRIMARY KEY(server_id, watch_id, summary_id)
);

CREATE TABLE sync_events(
    server_id CHAR(20) PRIMARY KEY,
    calendar_id VARCHAR(50),
    calendar_name VARCHAR(50),
    filter VARCHAR(50),
    delay INT,
    FOREIGN KEY(server_id) REFERENCES server_connexion(server_id)
);
