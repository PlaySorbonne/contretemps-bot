
import sqlite3




class Data: 
    
    def __init__(self):
        self.con = sqlite3.connect("data.db")
        self.con.row_factory = sqlite3.Row
        self.cur = self.con.cursor()
    
    
    @staticmethod
    def open_dict(d):
        return ','.join(':'+s for s in d)
    
    def check_server_connexion(self, server_id):
        res = self.cur.execute(f"SELECT gtoken,gmail FROM server_connexion WHERE server_id = '{server_id}'").fetchall()
        if res:
            return res[0]
        self.cur.execute(f"INSERT INTO server_connexion(server_id) VALUES ('{server_id}')")
        self.con.commit()
        return {'gtoken':None, 'gmail':None}
    
    def set_server_connexion(self, server_id, token, email):
        self.cur.execute(f"UPDATE server_connexion set gtoken='{token}', gmail='{email}' WHERE server_id = '{server_id}'")
        self.con.commit()
    
    def get_all(self, table):
        return self.cur.execute(f"SELECT * FROM {table}").fetchall()
    
    def insert_cols_in_table(self,table, cols):
        c = Data.open_dict(cols[0])
        #print('result of open_dict :', c, '\nLEN(COLS)=', )
        r = self.cur.executemany(f"INSERT INTO {table} VALUES({c})", cols)
        self.con.commit()
    
    

    def get_all_watched_cals(self, server_id):
        #print("Looking for server_id equals : ", server_id)
        #print("Doing request:", f"SELECT * FROM watched_calendar where server_id = '{server_id}'")
        val = self.cur.execute(f"SELECT * FROM watched_calendar where server_id = '{server_id}'").fetchall()
        #print(len(val))
        return val
    
    def get_all_watched_cals_for_cal(self, server_id, cal_id):
        #print("Request:", f"SELECT * FROM watched_calendar where server_id = '{server_id}' AND calendar_id = '{cal_id}'")
        res = self.cur.execute(f"SELECT * FROM watched_calendar where server_id = '{server_id}' AND calendar_id = '{cal_id}'").fetchall()
        #print("Result: ", [c for c in res[0]])
        return res
    
    def get_all_messages(self, server_id, watch_id):
        return self.cur.execute(f"SELECT * FROM message where server_id = '{server_id}' AND watch_id = '{watch_id}'").fetchall()
    
    def get_watch(self, server_id, watch_id):
        val = self.cur.execute(f"SELECT * FROM watched_calendar WHERE server_id = '{server_id}' AND watch_id = '{watch_id}'").fetchall()
        return None if len(val)==0 else val[0]
    #TODO EVERYWHERE : use sqlite3 formatter for arguments to avoid sql injections 
    def get_summary(self, server_id, watch_id):
        val = self.cur.execute(f"SELECT * FROM event_summary WHERE server_id = '{server_id}' AND watch_id = '{watch_id}'").fetchall()
        return None if len(val)==0 else val[0]

db = Data()
print(db.check_server_connexion("kwekwe")['gtoken'])
