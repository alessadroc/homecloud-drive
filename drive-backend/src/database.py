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
        cursor.execute("ALTER TABLE files ADD COLUMN IF NOT EXISTS size BIGINT DEFAULT 0")
        cursor.execute("ALTER TABLE files ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NULL")

        # Speeds up the listing queries once a user has a lot of files.
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_folder ON files (folder_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_folders_parent ON folders (parent_folder_id)")

        conn.commit()
        conn.close()

    # USERS

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

    # FOLDERS

    def get_root_folder_id(self, user_id: int):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "SELECT folder_id FROM folders WHERE user_id = %s AND is_root = TRUE",
                (user_id,)
            )
            row = cursor.fetchone()
            return row["folder_id"] if row else None
        except psycopg2.Error as e:
            print(f"Failed to fetch root folder: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def insert_folder(self, user_id: int, parent_folder_id: int, name: str):
        """Create a folder inside parent_folder_id. Returns the new folder_id."""
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                """
                INSERT INTO folders (user_id, parent_folder_id, name, is_root)
                VALUES (%s, %s, %s, FALSE)
                RETURNING folder_id
                """,
                (user_id, parent_folder_id, name)
            )
            folder_id = cursor.fetchone()["folder_id"]
            conn.commit()
            return folder_id
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Failed to create folder: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_folder(self, folder_id: int):
        """Full folder row - routes need name/parent/deleted_at, not just ownership."""
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute("SELECT * FROM folders WHERE folder_id = %s", (folder_id,))
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

    def get_folder_contents(self, folder_id: int):
        """Subfolders and files directly inside a folder. Excludes trashed items."""
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)

            cursor.execute(
                """
                SELECT * FROM folders
                WHERE parent_folder_id = %s AND deleted_at IS NULL
                ORDER BY name
                """,
                (folder_id,)
            )
            folders = cursor.fetchall()

            cursor.execute(
                """
                SELECT * FROM files
                WHERE folder_id = %s AND deleted_at IS NULL
                ORDER BY created_at DESC NULLS LAST, filename
                """,
                (folder_id,)
            )
            files = cursor.fetchall()

            return {"folder_id": folder_id, "folders": folders, "files": files}
        except psycopg2.Error as e:
            print(f"Failed to fetch folder contents: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_root_contents(self, user_id):
        """Contents of the user's root folder, in the shape the frontend expects."""
        root_folder_id = self.get_root_folder_id(user_id)
        if root_folder_id is None:
            return None

        contents = self.get_folder_contents(root_folder_id)
        if contents is None:
            return None

        return {
            "root_folder_id": root_folder_id,
            "folders": contents["folders"],
            "files": contents["files"],
        }

    def rename_folder(self, folder_id: int, name: str) -> bool:
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "UPDATE folders SET name = %s WHERE folder_id = %s AND is_root = FALSE",
                (name, folder_id)
            )
            changed = cursor.rowcount > 0
            conn.commit()
            return changed
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Failed to rename folder: {e}")
            return False
        finally:
            if conn:
                conn.close()

    # FILES

    def insert_file(self, user_id, folder_id, filename, file_uid, size=0):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                """
                INSERT INTO files (user_id, folder_id, filename, file_uid, size, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                RETURNING file_id
                """,
                (user_id, folder_id, filename, file_uid, size)
            )
            file_id = cursor.fetchone()["file_id"]
            conn.commit()
            return file_id
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
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

    def rename_file(self, file_id: int, filename: str) -> bool:
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "UPDATE files SET filename = %s WHERE file_id = %s",
                (filename, file_id)
            )
            changed = cursor.rowcount > 0
            conn.commit()
            return changed
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Failed to rename file: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def move_file(self, file_id: int, folder_id: int) -> bool:
        """Caller must confirm both the file and the destination folder belong
        to the requesting user before calling this."""
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "UPDATE files SET folder_id = %s WHERE file_id = %s",
                (folder_id, file_id)
            )
            changed = cursor.rowcount > 0
            conn.commit()
            return changed
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Failed to move file: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def move_folder(self, folder_id: int, new_parent_id: int) -> bool:
        """Re-parent a folder. Refuses to move a folder into itself or into
        one of its own descendants, which would cut that subtree off from
        the root - the rows would still exist but nothing could ever reach
        them by walking down from root."""
        conn = None
        try:
            if folder_id == new_parent_id:
                return False

            conn = self.get_conn()
            cursor = self._cursor(conn)

            # Walk up from the destination toward the root. If we pass through
            # folder_id on the way, the destination sits inside it.
            cursor.execute(
                """
                WITH RECURSIVE ancestors AS (
                    SELECT folder_id, parent_folder_id
                    FROM folders WHERE folder_id = %s
                    UNION ALL
                    SELECT f.folder_id, f.parent_folder_id
                    FROM folders f
                    JOIN ancestors a ON f.folder_id = a.parent_folder_id
                )
                SELECT 1 FROM ancestors WHERE folder_id = %s
                """,
                (new_parent_id, folder_id)
            )
            if cursor.fetchone() is not None:
                return False

            cursor.execute(
                """
                UPDATE folders SET parent_folder_id = %s
                WHERE folder_id = %s AND is_root = FALSE
                """,
                (new_parent_id, folder_id)
            )
            changed = cursor.rowcount > 0
            conn.commit()
            return changed
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Failed to move folder: {e}")
            return False
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
            if conn:
                conn.rollback()
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
            if conn:
                conn.rollback()
            print(f"Failed to delete the session: {e}")
        finally:
            if conn:
                conn.close()

    def trash_file(self, file_id: int) -> bool:
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "UPDATE files SET deleted_at = NOW() WHERE file_id = %s AND deleted_at IS NULL",
                (file_id,)
            )
            changed = cursor.rowcount > 0
            conn.commit()
            return changed
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Failed to trash the file {e}")
            return False
        finally:
            if conn:
                conn.close()

    def restore_file(self, file_id: int) -> bool:
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "UPDATE files SET deleted_at = NULL WHERE file_id = %s",
                (file_id,)
            )
            changed = cursor.rowcount > 0
            conn.commit()
            return changed
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Failed to restore file: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def trash_folder(self, folder_id: int) -> bool:
        """Trash a folder and the files directly inside it.

        Both UPDATEs run in one transaction, so NOW() returns the identical
        timestamp for the folder and its files. restore_folder uses that
        shared stamp to tell 'trashed with the folder' apart from 'trashed
        on its own earlier', and only brings back the former.

        NOTE: only cascades one level. If nested folders are added later,
        this needs to recurse into subfolders and their files too.
        """
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)

            cursor.execute(
                """
                UPDATE folders SET deleted_at = NOW()
                WHERE folder_id = %s AND is_root = FALSE AND deleted_at IS NULL
                """,
                (folder_id,)
            )
            changed = cursor.rowcount > 0

            if changed:
                cursor.execute(
                    """
                    UPDATE files SET deleted_at = NOW()
                    WHERE folder_id = %s AND deleted_at IS NULL
                    """,
                    (folder_id,)
                )

            conn.commit()
            return changed
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Failed to trash folder: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def restore_folder(self, folder_id: int) -> bool:
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)

            cursor.execute(
                "SELECT deleted_at FROM folders WHERE folder_id = %s",
                (folder_id,)
            )
            row = cursor.fetchone()
            if row is None or row["deleted_at"] is None:
                return False
            stamp = row["deleted_at"]

            cursor.execute(
                "UPDATE files SET deleted_at = NULL WHERE folder_id = %s AND deleted_at = %s",
                (folder_id, stamp)
            )
            cursor.execute(
                "UPDATE folders SET deleted_at = NULL WHERE folder_id = %s",
                (folder_id,)
            )

            conn.commit()
            return True
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Failed to restore folder: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def get_trashed_items(self, user_id: int):
        """Everything in the user's trash, newest first."""
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)

            cursor.execute(
                """
                SELECT * FROM folders
                WHERE user_id = %s AND deleted_at IS NOT NULL AND is_root = FALSE
                ORDER BY deleted_at DESC
                """,
                (user_id,)
            )
            folders = cursor.fetchall()

            cursor.execute(
                """
                SELECT * FROM files
                WHERE user_id = %s AND deleted_at IS NOT NULL
                ORDER BY deleted_at DESC
                """,
                (user_id,)
            )
            files = cursor.fetchall()

            return {"folders": folders, "files": files}
        except psycopg2.Error as e:
            print(f"Failed to fetch trash: {e}")
            return None
        finally:
            if conn:
                conn.close()

    def get_expired_files(self, cutoff_days: int = 30):
        """Files trashed longer ago than cutoff_days. Returns enough to
        delete the bytes from disk as well as the row."""
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                """
                SELECT file_id, user_id, file_uid FROM files
                WHERE deleted_at IS NOT NULL
                  AND deleted_at < NOW() - (%s * INTERVAL '1 day')
                """,
                (cutoff_days,)
            )
            return cursor.fetchall()
        except psycopg2.Error as e:
            print(f"Failed to fetch expired files: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def get_expired_folders(self, cutoff_days: int = 30):
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                """
                SELECT folder_id FROM folders
                WHERE deleted_at IS NOT NULL
                  AND is_root = FALSE
                  AND deleted_at < NOW() - (%s * INTERVAL '1 day')
                """,
                (cutoff_days,)
            )
            return cursor.fetchall()
        except psycopg2.Error as e:
            print(f"Failed to fetch expired folders: {e}")
            return []
        finally:
            if conn:
                conn.close()

    def permanently_delete_file(self, file_id: int) -> bool:
        """Removes the row only. Delete the bytes from storage separately."""
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute("DELETE FROM files WHERE file_id = %s", (file_id,))
            changed = cursor.rowcount > 0
            conn.commit()
            return changed
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Failed to permanently delete file: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def permanently_delete_folder(self, folder_id: int) -> bool:
        """Only succeeds once the folder holds no file rows - files.folder_id
        has a foreign key onto folders, so purge files first."""
        conn = None
        try:
            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                "DELETE FROM folders WHERE folder_id = %s AND is_root = FALSE",
                (folder_id,)
            )
            changed = cursor.rowcount > 0
            conn.commit()
            return changed
        except psycopg2.Error as e:
            if conn:
                conn.rollback()
            print(f"Failed to permanently delete folder: {e}")
            return False
        finally:
            if conn:
                conn.close()

    def search_files(self, user_id: int, term: str, limit: int = 50):
        """Filename search across all of a user's folders - exlcuding trash"""
        conn = None
        try:
            # % and _ are wildcards in LIKE. Someone searching "report_final"
            # means a literal underscore, so escape them before building the
            # pattern or the search quietly matches more than they asked for.
            escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"

            conn = self.get_conn()
            cursor = self._cursor(conn)
            cursor.execute(
                """
                SELECT f.*, fo.name AS folder_name, fo.is_root AS folder_is_root
                FROM files f
                JOIN folders fo ON fo.folder_id = f.folder_id
                WHERE f.user_id = %s
                    AND f.deleted_at IS NULL
                    AND f.filename ILIKE %s ESCAPE '\\'
                ORDER BY f.created_at DESC NULLS LAST, f.filename
                LIMIT %s
                """,
                (user_id, pattern, limit)
            )
            return cursor.fetchall()
        except psycopg2.Error as e:
            print(f"Search failed: {e}")
            return []
        finally:
            if conn:
                conn.close()