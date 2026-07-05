"""
Database connector — Executes queries against PostgreSQL, MySQL, and SQLite databases.
"""
try:
    import sqlite3
except ImportError:
    sqlite3 = None

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None
    RealDictCursor = None

try:
    import pymysql
except ImportError:
    pymysql = None


class DatabaseMixin:
    """Mixin providing database query execution for the main app."""

    def run_db_query(self, conn_type, conn_config, query_text):
        if conn_type == 'sqlite':
            if sqlite3 is None:
                raise ImportError("sqlite3 module not available.")
            db_path = conn_config.get("filepath", "")
            if not db_path:
                raise ValueError("SQLite database path not provided.")
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(query_text)
            
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
                result = {"rows": rows, "rows_affected": len(rows), "status": "success"}
            else:
                conn.commit()
                result = {"rows_affected": cursor.rowcount, "status": "success"}
                
            cursor.close()
            conn.close()
            return result
            
        elif conn_type == 'postgres':
            if psycopg2 is None:
                raise ImportError("psycopg2 library not installed.\nTo use real PostgreSQL connections, install it via: pip install psycopg2-binary")
            host = conn_config.get("host", "localhost")
            port = conn_config.get("port", "5432")
            database = conn_config.get("database", "")
            user = conn_config.get("user", "")
            password = conn_config.get("password", "")
            
            conn = psycopg2.connect(host=host, port=port, database=database, user=user, password=password)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            cursor.execute(query_text)
            
            if cursor.description:
                rows = [dict(row) for row in cursor.fetchall()]
                result = {"rows": rows, "rows_affected": len(rows), "status": "success"}
            else:
                conn.commit()
                result = {"rows_affected": cursor.rowcount, "status": "success"}
                
            cursor.close()
            conn.close()
            return result
            
        elif conn_type == 'mysql':
            if pymysql is None:
                raise ImportError("pymysql library not installed.\nTo use real MySQL connections, install it via: pip install pymysql")
            host = conn_config.get("host", "localhost")
            port = conn_config.get("port", "3306")
            database = conn_config.get("database", "")
            user = conn_config.get("user", "")
            password = conn_config.get("password", "")
            
            conn = pymysql.connect(
                host=host, port=int(port), database=database, user=user, password=password,
                cursorclass=pymysql.cursors.DictCursor
            )
            cursor = conn.cursor()
            cursor.execute(query_text)
            
            if cursor.description:
                rows = [dict(row) for row in cursor.fetchall()]
                result = {"rows": rows, "rows_affected": len(rows), "status": "success"}
            else:
                conn.commit()
                result = {"rows_affected": cursor.rowcount, "status": "success"}
                
            cursor.close()
            conn.close()
            return result
            
        raise ValueError(f"Unknown database type: {conn_type}")

    def get_db_schema(self, conn_type, conn_config):
        if conn_type == 'sqlite':
            if sqlite3 is None:
                raise ImportError("sqlite3 module not available.")
            db_path = conn_config.get("filepath", "")
            if not db_path:
                raise ValueError("SQLite database path not provided.")
                
            import os
            if not os.path.exists(db_path):
                raise FileNotFoundError(f"SQLite file not found: {db_path}")
                
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in cursor.fetchall()]
            
            schema = {}
            for table in tables:
                cursor.execute(f"PRAGMA table_info([{table}]);")
                schema[table] = [row[1] for row in cursor.fetchall()]
                
            cursor.close()
            conn.close()
            return schema
            
        elif conn_type == 'postgres':
            if psycopg2 is None:
                raise ImportError("psycopg2 library not installed.\nTo use real PostgreSQL connections, install it via: pip install psycopg2-binary")
            host = conn_config.get("host", "localhost")
            port = conn_config.get("port", "5432")
            database = conn_config.get("database", "")
            user = conn_config.get("user", "")
            password = conn_config.get("password", "")
            
            conn = psycopg2.connect(host=host, port=port, database=database, user=user, password=password)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute("""
                SELECT table_name, column_name 
                FROM information_schema.columns 
                WHERE table_schema = 'public'
                ORDER BY table_name, ordinal_position;
            """)
            rows = cursor.fetchall()
            
            schema = {}
            for row in rows:
                t_name = row['table_name']
                c_name = row['column_name']
                if t_name not in schema:
                    schema[t_name] = []
                schema[t_name].append(c_name)
                
            cursor.close()
            conn.close()
            return schema
            
        elif conn_type == 'mysql':
            if pymysql is None:
                raise ImportError("pymysql library not installed.\nTo use real MySQL connections, install it via: pip install pymysql")
            host = conn_config.get("host", "localhost")
            port = conn_config.get("port", "3306")
            database = conn_config.get("database", "")
            user = conn_config.get("user", "")
            password = conn_config.get("password", "")
            
            conn = pymysql.connect(
                host=host, port=int(port), database=database, user=user, password=password,
                cursorclass=pymysql.cursors.DictCursor
            )
            cursor = conn.cursor()
            cursor.execute("""
                SELECT table_name, column_name 
                FROM information_schema.columns 
                WHERE table_schema = DATABASE()
                ORDER BY table_name, ordinal_position;
            """)
            rows = cursor.fetchall()
            
            schema = {}
            for row in rows:
                t_name = row['table_name']
                c_name = row['column_name']
                if t_name not in schema:
                    schema[t_name] = []
                schema[t_name].append(c_name)
                
            cursor.close()
            conn.close()
            return schema
            
        raise ValueError(f"Unknown database type: {conn_type}")
