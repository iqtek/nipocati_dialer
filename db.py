# coding: utf-8

import MySQLdb


class DB:
    conn = None

    def __init__(self):
        self._host = 'localhost'
        self._user = 'root'
        self._password = ''
        self._db = ''

    def connect(self):
        try:
            self.conn = MySQLdb.Connection(
                host=self._host, user=self._user, passwd=self._password, db=self._db)
        except:
            return None
        return self

    def close(self):
        self.conn.close()

    def connected(self):
        if self.conn == None:
            return False
        return True

    def query(self, sql):
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
            self.conn.commit()
        except (AttributeError, MySQLdb.OperationalError):
            self.connect()
            cursor = self.conn.cursor()
            cursor.execute(sql)
            self.conn.commit()

        return cursor

    def host(self, host):
        self._host = host
        return self

    def user(self, user):
        self._user = user
        return self

    def password(self, password):
        self._password = password
        return self

    def db(self, db):
        self._db = db
        return self
