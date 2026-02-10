# extensions.py
import mysql.connector as mysql_connector
from flask import current_app
from flask import g

def get_mysql_connection():
    if 'mysql_conn' not in g:
        cfg = current_app.config
        g.mysql_conn = mysql_connector.connect(
            host=cfg.get("MYSQL_HOST", "localhost"),
            user=cfg.get("MYSQL_USER", "root"),
            password=cfg.get("MYSQL_PASSWORD", ""),
            database=cfg.get("MYSQL_DB", "library_management_system"),
            port=int(cfg.get("MYSQL_PORT", 3306)),
        )
    return g.mysql_conn


class MySQLCompat:
    """
    Minimal compatibility layer for code that expects mysql.connection.cursor().
    Uses mysql.connector under the hood.
    """
    @property
    def connection(self):
        return get_mysql_connection()


mysql = MySQLCompat()
