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


import sqlite3




class Data: 
    """
    Wrapper for every used SQL request
    """
    
    def __init__(self):
        self.con = sqlite3.connect("data.db")
        self.con.row_factory = sqlite3.Row
        self.cur = self.con.cursor()
    
    @staticmethod
    def open_dict(d):
        return ','.join(':'+s for s in d)
    
    
    def check_server_connexion(self, server_id):
        res = self.cur.execute(f"SELECT gtoken,gmail FROM server_connexion WHERE server_id = ?", (server_id,)).fetchall()
        if res:
            return res[0]
        self.cur.execute(f"INSERT INTO server_connexion(server_id) VALUES (?)", (server_id,))
        self.con.commit()
        return {'gtoken':None, 'gmail':None}
    
    
    def set_server_connexion(self, server_id, token, email):
        self.cur.execute(f"UPDATE server_connexion set gtoken= ?, gmail= ? WHERE server_id = ?", (token, email, server_id))
        self.con.commit()
    
    
    def get_all(self, table):
        return self.cur.execute(f"SELECT * FROM {table}").fetchall()
    
    
    def insert_cols_in_table(self,table, cols):
        c = Data.open_dict(cols[0])
        r = self.cur.executemany(f"INSERT INTO {table} VALUES({c})", cols)
        self.con.commit()
    
    
    def get_all_watched_cals(self, server_id):
        val = self.cur.execute(f"SELECT * FROM watched_calendar where server_id = ? ", (server_id,)).fetchall()
        return val
    
    
    def get_all_watched_cals_for_cal(self, server_id, cal_id):
        res = self.cur.execute(f"SELECT * FROM watched_calendar where server_id = ? AND calendar_id = ?", (server_id, cal_id)).fetchall()
        return res
    
    
    def get_watch(self, server_id, watch_id):
        val = self.cur.execute(f"SELECT * FROM watched_calendar WHERE server_id = ? AND watch_id = ?", (server_id, watch_id)).fetchall()
        return None if len(val)==0 else val[0] 
    
    
    def delete_watch(self, server_id, watch_id):
        self.cur.execute('DELETE FROM watched_calendar WHERE server_id = ? AND watch_id = ?', (server_id, watch_id))
        self.con.commit()
    
    
    def get_summary(self, server_id, watch_id, summary_id):
        val = self.cur.execute("SELECT * FROM event_summary WHERE server_id = ? AND watch_id = ? AND summary_id = ?", (server_id, watch_id, summary_id)).fetchall()
        return None if len(val)==0 else val[0]
    
    
    def delete_summary(self, server_id, watch_id, summary_id):
        val = self.cur.execute("DELETE FROM event_summary WHERE server_id = ? AND watch_id = ? AND summary_id = ?", (server_id, watch_id, summary_id))
        self.con.commit()
    
    
    def get_watch_summaries(self, server_id, watch_id):
        val = self.cur.execute("SELECT * FROM event_summary WHERE server_id = ? AND watch_id = ?", (server_id, watch_id)).fetchall()
        return val
    
    
    def modify_summary_message(self, summary, new_message):
        val = self.cur.execute(
            """UPDATE event_summary
               SET message_id = ?
               WHERE server_id = ? AND watch_id = ? AND summary_id = ?""", 
            (new_message, summary['server_id'], summary['watch_id'], summary['summary_id'])
        )
        self.con.commit()
    
    
    def modify_summary(self, summary, new_data):
        mods = " , ".join( f"{key} = ?" for key in new_data)
        val = self.cur.execute(
            f"""UPDATE event_summary
               SET {mods}
               WHERE server_id = ? AND watch_id = ? AND summary_id = ?""",
            [d for d in new_data.values()] + [summary['server_id'], summary['watch_id'], summary['summary_id']]
        )
        self.con.commit()
    
    
    def delete_access(self, server_id, thing_id):
        self.cur.execute(
            "DELETE FROM user_access WHERE server_id = ? AND thing_id = ?",
            (server_id, thing_id)
        )
        self.con.commit()
    
    
    def set_access(self, server_id, thing_id, mention, access_level):
        v = self.cur.execute(
            "SELECT * FROM user_access WHERE server_id = ? AND thing_id = ?",
            (server_id, thing_id)        
        ).fetchall()
        if len(v):
            self.cur.execute(
                """UPDATE user_access
                   SET mention = ?, access_level = ?
                   WHERE server_id = ? AND thing_id = ?""",
                (mention, access_level, server_id, thing_id)
            )
        else:
            self.cur.execute(
                "INSERT INTO user_access VALUES (?,?,?,?)",
                (server_id,thing_id,mention,access_level)
            )
        self.con.commit()


    def get_access(self, server_id, thing_id):
        t = self.cur.execute(
            "SELECT access_level FROM user_access WHERE server_id = ? AND thing_id = ?",
            (server_id, thing_id)
        ).fetchall()
        if len(t):
            return t[0]['access_level']
        else:
            return 0
    
    
    def get_access_levels(self, server_id):
        res = self.cur.execute(
            "SELECT * from user_access WHERE server_id = ?",
            (server_id,)
        ).fetchall()
        return res

