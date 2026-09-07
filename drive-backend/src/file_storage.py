import os
import uuid
import shutil


class FileStorage:
    """Blob storage on disk. Files are keyed by a generated UUID, never by
    the name the user gave them, and every user's blobs live in their own
    directory under root_dir."""

    def __init__(self, root_dir: str):
        if not root_dir:
            raise ValueError("FileStorage needs a root_dir (is STORAGE_ROOT set?)")
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)

    def _user_root_path(self, user_id) -> str:
        return os.path.join(self.root_dir, str(user_id))

    def _resolve(self, user_id, storage_name: str) -> str:
        """Build the on-disk path for a blob, refusing anything that isn't a
        bare filename. storage_name always comes from our own database, but a
        storage layer shouldn't rely on its caller for that: a value like
        '../../etc/passwd' would otherwise escape the storage tree."""
        if not storage_name or os.path.basename(storage_name) != storage_name:
            raise ValueError(f"Unsafe storage name: {storage_name!r}")
        return os.path.join(self._user_root_path(user_id), storage_name)

    def create_user_root(self, user_id) -> str:
        """Creates the on-disk directory for a user. Called once at signup."""
        user_root = self._user_root_path(user_id)
        os.makedirs(user_root, exist_ok=True)
        return user_root

    def save_file(self, user_id, file_obj) -> dict:
        """Write an uploaded file into the user's directory."""
        user_dir = self._user_root_path(user_id)
        os.makedirs(user_dir, exist_ok=True)

        storage_name = str(uuid.uuid4())
        dest_path = os.path.join(user_dir, storage_name)
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file_obj, f)

        return {
            "storage_name": storage_name,
            "storage_size": int(os.path.getsize(dest_path)),
        }

    def make_directory(self, user_id, file_obj):
        ...
    
    def read_file(self, user_id, storage_name: str):
        path = self._resolve(user_id, storage_name)
        if not os.path.exists(path):
            return None
        return open(path, "rb")

    def file_exists(self, user_id, storage_name: str) -> bool:
        return os.path.exists(self._resolve(user_id, storage_name))

    def delete_file(self, user_id, storage_name: str) -> bool:
        """Remove a blob. Returns True when the path is clear afterwards,
        including when the file was already gone - deleting something twice
        should not be an error. Returns False only on a real OS failure
        (permissions, I/O), so a caller can leave the database row alone and
        retry on the next sweep.
        """
        try:
            path = self._resolve(user_id, storage_name)
        except ValueError as e:
            print(f"Refusing to delete: {e}")
            return False

        try:
            os.remove(path)
            return True
        except FileNotFoundError:
            # Worth logging: the database thinks this blob exists and it
            # doesn't, which means storage and metadata have drifted.
            print(f"Blob already missing: {path}")
            return True
        except OSError as e:
            print(f"Failed to delete {path}: {e}")
            return False

    def size_of(self, user_id, storage_name: str) -> int:
        """Bytes on disk, or 0 if the blob is missing."""
        try:
            return int(os.path.getsize(self._resolve(user_id, storage_name)))
        except (OSError, ValueError):
            return 0

    def usage_for_user(self, user_id) -> int:
        """Total bytes this user occupies on disk. Reads the filesystem
        directly rather than summing the size column, so it stays honest if
        the two ever disagree."""
        user_dir = self._user_root_path(user_id)
        total = 0
        try:
            with os.scandir(user_dir) as entries:
                for entry in entries:
                    if entry.is_file():
                        total += entry.stat().st_size
        except FileNotFoundError:
            return 0
        return total