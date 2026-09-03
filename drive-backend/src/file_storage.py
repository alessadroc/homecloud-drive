import os
import uuid
import shutil

class FileStorage:
    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        os.makedirs(self.root_dir, exist_ok=True)

    def _path_for(self, storage_name: str) -> str:
        return os.path.join(self.root_dir, storage_name)

    def _user_root_path(self, user_id) -> str:
        return os.path.join(self.root_dir, str(user_id))

    def create_user_root(self, user_id) -> str:
        """Creates the on-disk directory for a user. Called once at signup."""
        user_root = self._user_root_path(user_id)
        os.makedirs(user_root, exist_ok=True)
        return user_root

    def save_file(self, user_id, file_obj) -> str:
        storage_name = str(uuid.uuid4())
        dest_path = os.path.join(self._user_root_path(user_id), storage_name)
        with open(dest_path, "wb") as f:
            shutil.copyfileobj(file_obj, f)
        return storage_name

    def read_file(self, user_id, storage_name: str):
        path = os.path.join(self._user_root_path(user_id), storage_name)
        if not os.path.exists(path):
            return None
        return open(path, "rb")

    def delete_file(self, user_id, storage_name: str) -> bool:
        path = os.path.join(self._user_root_path(user_id), storage_name)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def file_exists(self, user_id, storage_name: str) -> bool:
        return os.path.exists(os.path.join(self._user_root_path(user_id), storage_name))