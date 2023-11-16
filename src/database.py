
import sqlite3




class Data: 
    
    def __init__(self):
        self.con = sqlite3.connect("data.db")
        self.con.row_factory = sqlite3.Row
        self.cur = self.con.cursor()
    
    
    @staticmethod
    def open_dict(d):
        ','.join(':'+s for s in d)
    
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
    
    def insert_cols_in_table(table, cols):
        c = open_dict(cols)
        print(c)
        return self.cur.executemany(f"INSERT INTO {table} VALUES({c})", cols)

    def get_all_watched_cals(self, server_id):
        return self.cur.execute(f"SELECT * FROM watch_calendar where server_id = '{server_id}'").fetchall()
    
    def get_all_watched_cals_for_cal(self, server_id, cal_id):
        return self.cur.execute(f"SELECT * FROM watch_calendar where server_id = '{server_id}' AND calendar_id = '{cal_id}'").fetchall()
    
    def get_all_messages(self, server_id, watch_id):
        return self.cur.execute(f"SELECT * FROM message where server_id = '{server_id}' AND watch_id = '{watch_id}'").fetchall()
    
    

db = Data()
print(db.check_server_connexion("kwekwe")['gtoken'])
