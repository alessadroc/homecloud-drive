import psycopg2
import psycopg2.extras
import os
import secrets
from datetime import datetime
from dotenv import load_dotenv
from psycopg2.errors import UniqueViolation
from psycopg2.extensions import connection

load_dotenv()

class Database:
    def __init__(self):
        self.conn_params = {
            "dbname": os.getenv("DB_NAME"),
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "host": os.getenv("DB_HOST", "localhost"),
            "port": os.getenv("DB_PORT", "5432"),
        }
        self._create_tables()

    def get_conn(self) -> connection:
        return psycopg2.connect(**self.conn_params)

    def _cursor(self, conn):
        """Return a cursor whose rows come back as dicts keyed by column name."""
        return conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    def _create_tables(self):
        conn = self.get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                hashed_password TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS folders (
                folder_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                parent_folder_id INTEGER REFERENCES folders(folder_id),
                name TEXT,
                is_root BOOLEAN DEFAULT FALSE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS files (
                file_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                folder_id INTEGER REFERENCES folders(folder_id) NOT NULL,
                filename TEXT NOT NULL,
                file_uid TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                created_at TIMESTAMP
            )
        """)

        # --- Schema patches: safe to re-run, only adds what's missing ---
        cursor.execute("ALTER TABLE folders ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP DEFAULT NULL")
        cursor.execute("ALTER TABLE files ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP DEFAULT NULL")

        conn.commit()
        conn.close()

    def insert_user(self, username, hashed_password):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)

            cursor.execute(
                """
                INSERT INTO users (username, hashed_password)
                VALUES (%s, %s)
                RETURNING id
                """,
                (username, hashed_password)
            )
            user_id = cursor.fetchone()["id"]

            cursor.execute(
                """
                INSERT INTO folders
                (user_id, parent_folder_id, name, is_root)
                VALUES (%s, %s, %s, %s)
                """,
                (user_id, None, "root", True)
            )

            conn.commit()
            return user_id

        except UniqueViolation:
            if conn:
                conn.rollback()
            return "That username is already in use."

        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Database error: {e}")
            return None

        finally:
            if conn:
                conn.close()

    def get_user_by_username(self, username):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            return cursor.fetchone()
        except psycopg2.Error as e:
            print(f"Failed to lookup user: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_all_users(self):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute("SELECT * FROM users")
            return cursor.fetchall()
        except psycopg2.Error as e:
            print(f"Failed to fetch users: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_root_contents(self, user_id):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)

            # 1. Find the user's root folder
            cursor.execute(
                "SELECT folder_id FROM folders WHERE user_id = %s AND is_root = TRUE",
                (user_id,)
            )
            root = cursor.fetchone()
            if root is None:
                return None
            root_folder_id = root["folder_id"]

            # 2. Get subfolders inside root (excluding trashed)
            cursor.execute(
                "SELECT * FROM folders WHERE parent_folder_id = %s AND deleted_at IS NULL",
                (root_folder_id,)
            )
            folders = cursor.fetchall()

            # 3. Get files inside root (excluding trashed)
            cursor.execute(
                "SELECT * FROM files WHERE folder_id = %s AND deleted_at IS NULL",
                (root_folder_id,)
            )
            files = cursor.fetchall()

            return {"root_folder_id": root_folder_id, "folders": folders, "files": files}
        except psycopg2.Error as e:
            print(f"Failed to fetch root contents: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_folder(self, folder_id: int):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "SELECT folder_id, user_id FROM folders WHERE folder_id = %s",
                (folder_id,)
            )
            return cursor.fetchone()
        except psycopg2.Error as e:
            print(f"Failed to fetch folder: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_folders(self, user_id: int):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "SELECT * FROM folders WHERE user_id = %s AND deleted_at IS NULL",
                (user_id,)
            )
            return cursor.fetchall()
        except psycopg2.Error as e:
            print(f"Failed to fetch folders: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_files(self, user_id: int):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "SELECT * FROM files WHERE user_id = %s AND deleted_at IS NULL",
                (user_id,)
            )
            return cursor.fetchall()
        except psycopg2.Error as e:
            print(f"Failed to fetch files: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def insert_file(self, user_id, folder_id, filename, file_uid):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                """
                INSERT INTO files (user_id, folder_id, filename, file_uid)
                VALUES (%s, %s, %s, %s)
                RETURNING file_id
                """,
                (user_id, folder_id, filename, file_uid)
            )
            file_id = cursor.fetchone()["file_id"]
            conn.commit()
            return file_id
        except psycopg2.Error as e:
            print(f"Failed to insert file: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_file(self, file_id):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute("SELECT * FROM files WHERE file_id = %s", (file_id,))
            return cursor.fetchone()
        except psycopg2.Error as e:
            print(f"Failed to fetch file {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_user_by_token(self, token: str):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "SELECT user_id FROM sessions WHERE token = %s",
                (token,)
            )
            row = cursor.fetchone()
            return row["user_id"] if row else None
        except psycopg2.Error as e:
            print(f"Failed to look up session: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def insert_session(self, user_id: int) -> str:
        conn = None
        token = secrets.token_urlsafe(32)
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "INSERT INTO sessions (token, user_id, created_at) VALUES (%s, %s, %s)",
                (token, user_id, datetime.now())
            )
            conn.commit()
            return token
        except psycopg2.Error as e:
            print(f"Failed to create session: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def delete_session(self, token: str):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute("DELETE FROM sessions WHERE token = %s", (token,))
            conn.commit()
        except psycopg2.Error as e:
            print(f"Failed to delete the session: {e}")
        finally:
            if conn:
                conn.close()

    def trash_file(self, file_id: int):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "UPDATE files SET deleted_at = NOW() WHERE file_id = %s",
                (file_id,)
            )
            conn.commit()
        except psycopg2.Error as e:
            print(f"Failed to trash the file {e}")
        finally:
            if conn:
                conn.close()

    def restore_file(self, file_id: int):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "UPDATE files SET deleted_at = NULL WHERE file_id = %s",
                (file_id,)
            )
            conn.commit()
        except psycopg2.Error as e:
            print(f"Failed to restore file: {e}")
        finally:
            if conn:
                conn.close()

    def trash_folder(self, folder_id: int):
        # NOTE: only cascades one level. If nested folders are added later,
        # this needs to recursively trash subfolders + their files too.
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "UPDATE folders SET deleted_at = NOW() WHERE folder_id = %s",
                (folder_id,)
            )
            cursor.execute(
                "UPDATE files SET deleted_at = NOW() WHERE folder_id = %s",
                (folder_id,)
            )
            conn.commit()
        except psycopg2.Error as e:
            print(f"Failed to trash folder: {e}")
        finally:
            if conn:
                conn.close()

    def restore_folder(self, folder_id: int):
        # NOTE: only cascades one level, matching trash_folder.
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "UPDATE folders SET deleted_at = NULL WHERE folder_id = %s",
                (folder_id,)
            )
            cursor.execute(
                "UPDATE files SET deleted_at = NULL WHERE folder_id = %s",
                (folder_id,)
            )
            conn.commit()
        except psycopg2.Error as e:
            print(f"Failed to restore folder: {e}")
        finally:
            if conn:
                conn.close()