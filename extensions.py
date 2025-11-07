# extensions.py
from flask_mysqldb import MySQL
import mysql.connector
from flask import current_app
from flask import g

mysql = MySQL()


from flask import g
import mysql.connector

def get_mysql_connection():
    if 'mysql_conn' not in g:
        g.mysql_conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="library_management_system"
        )
    return g.mysql_conn
