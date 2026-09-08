from file_storage import FileStorage
from passlib.context import CryptContext
from dotenv import load_dotenv
import os

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from database import Database
from contextlib import asynccontextmanager
from cleanup import purge_trash

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(purge_trash(db, storage))
    yield

load_dotenv()
app = FastAPI(lifespan=lifespan)
db = Database()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
storage = FileStorage(root_dir=os.getenv("STORAGE_ROOT"))
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],  # dev + prod frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    token = credentials.credentials
    user_id = db.get_user_by_token(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user_id


@app.get("/")
def read_root():
    return {"status": "ok", "message": "FastAPI Service: You have created a FastAPI Service"}


# --- Unprotected routes (no token needed - these are how you GET a token) ---

@app.post("/sign-up")
def sign_up(username: str, password: str) -> dict:
    if db.get_user_by_username(username):
        raise HTTPException(status_code=400, detail="Username already taken")

    hashed = pwd_context.hash(password)
    user_id = db.insert_user(username, hashed)
    storage.create_user_root(user_id)
    return {"status": "ok", "message": "User created.", "id": user_id}


@app.post("/sign-in")
def sign_in(username: str, password: str):
    user = db.get_user_by_username(username)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not pwd_context.verify(password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = db.insert_session(user["id"])
    return {"status": "ok", "message": "Logged in.", "token": token}


# --- Protected routes (require a valid Bearer token) ---

@app.get("/get-root-contents")
def get_root_contents(user_id: int = Depends(_get_current_user_id)) -> dict:
    contents = db.get_root_contents(user_id)
    if contents is None:
        raise HTTPException(status_code=404, detail="Root folder not found")
    return contents


@app.post("/files")
def upload_file(
    folder_id: int = Form(...),
    file: UploadFile = File(...),
    user_id: int = Depends(_get_current_user_id)
):
    folder = db.get_folder(folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    if folder["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="This folder does not belong to you")

    storage_params = storage.save_file(user_id, file.file)

    file_id = db.insert_file(
        user_id=user_id,
        folder_id=folder_id,
        filename=file.filename,
        file_uid=storage_params['storage_name'],
        size=storage_params['storage_size']
    )
    return {
        "status": "ok",
        "message": "File uploaded.",
        "file_id": file_id,
        "filename": file.filename,
        "params" : storage_params
    }


@app.post("/logout")
def logout(credentials: HTTPAuthorizationCredentials = Depends(security)):
    db.delete_session(credentials.credentials)
    return {"status": "ok", "message": "Logged out."}


@app.get("/files/{file_id}/download")
def download_file(file_id: int, user_id: int = Depends(_get_current_user_id)):
    file_row = db.get_file(file_id)
    if file_row is None:
        raise HTTPException(status_code=404, detail="File not found")
    if file_row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="This file does not belong to you")

    storage_name = file_row["file_uid"]
    filename = file_row["filename"]
    file_obj = storage.read_file(user_id, storage_name)
    if file_obj is None:
        raise HTTPException(status_code=404, detail="File missing from storage")
    return StreamingResponse(
        file_obj,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@app.post("/files/{file_id}/move")
def move_file(
    file_id: int,
    folder_id: int = Form(...),
    user_id: int = Depends(_get_current_user_id)
):
    file_row = db.get_file(file_id)
    if file_row is None:
        raise HTTPException(status_code=404, detail="File not found")
    if file_row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="This file does not belong to you")

    destination = db.get_folder(folder_id)
    if destination is None:
        raise HTTPException(status_code=404, detail="Destination folder not found")
    if destination["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="That folder does not belong to you")
    if destination["deleted_at"] is not None:
        raise HTTPException(status_code=400, detail="That folder is in the trash")

    if not db.move_file(file_id, folder_id):
        raise HTTPException(status_code=500, detail="Couldn't move the file")

    return {"status": "ok", "message": "File moved."}

@app.delete("/files/{file_id}")
def delete_file(file_id: int, user_id: int = Depends(_get_current_user_id)):
    file_row = db.get_file(file_id)
    if file_row is None:
        raise HTTPException(status_code=404, detail="File not found")
    if file_row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="This file does not belong to you")
    db.trash_file(file_id)
    return {"status": "ok", "message": "File moved to trash."}


@app.post("/files/{file_id}/restore")
def restore_file(file_id: int, user_id: int = Depends(_get_current_user_id)):
    file_row = db.get_file(file_id)
    if file_row is None:
        raise HTTPException(status_code=404, detail="File not found")
    if file_row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="This file does not belong to you")
    db.restore_file(file_id)
    return {"status": "ok", "message": "File restored."}

@app.post("/folders")
def create_folder(
    name: str = Form(...),
    parent_folder_id: int = Form(...),
    user_id: int = Depends(_get_current_user_id)
):
    parent = db.get_folder(parent_folder_id)
    if parent is None:
        raise HTTPException(status_code=404, detail="Parent folder not found")
    if parent["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="This folder does not belong to you")
    if parent["deleted_at"] is not None:
        raise HTTPException(status_code=400, detail="That folder is in the trash")

    name = name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Give the folder a name")

    folder_id = db.insert_folder(user_id, parent_folder_id, name)
    if folder_id is None:
        raise HTTPException(status_code=500, detail="Couldn't create the folder")

    return {"status": "ok", "message": "Folder created", "folder_id": folder_id}

@app.get("/folders/{folder_id}/contents")
def folder_contents(folder_id: int, user_id: int = Depends(_get_current_user_id)):
    folder = db.get_folder(folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    if folder["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="This folder does not belong to you")
    if folder["deleted_at"] is not None:
        raise HTTPException(status_code=404, detail="That folder is in the trash")

    contents = db.get_folder_contents(folder_id)
    if contents is None:
        raise HTTPException(status_code=500, detail="Couldn't read that folder")
    return contents

@app.delete("/folders/{folder_id}")
def delete_folder(folder_id: int, user_id: int = Depends(_get_current_user_id)):
    folder = db.get_folder(folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    if folder["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="This folder does not belong to you")
    db.trash_folder(folder_id)
    return {"status": "ok", "message": "Folder moved to trash."}


@app.post("/folders/{folder_id}/restore")
def restore_folder(folder_id: int, user_id: int = Depends(_get_current_user_id)):
    folder = db.get_folder(folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    if folder["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="This folder does not belong to you")
    db.restore_folder(folder_id)
    return {"status": "ok", "message": "Folder restored."}

@app.get("/trash")
def list_trash(user_id: int = Depends(_get_current_user_id)):
    items = db.get_trashed_items(user_id)
    if items is None:
        raise HTTPException(status_code=500, detail="Couldn't read the trash")
    return items


@app.post("/files/{file_id}/restore")
def restore_file(file_id: int, user_id: int = Depends(_get_current_user_id)):
    file_row = db.get_file(file_id)
    if file_row is None:
        raise HTTPException(status_code=404, detail="File not found")
    if file_row["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="This file does not belong to you")

    # If the folder it came from is still in the trash restoring in place
    # would leave the file still marked as trash, so put it back at the root instead
    parent = db.get_folder(file_row["folder_id"])
    if parent is None or parent["deleted_at"] is not None:
        root_id = db.get_root_folder_id(user_id)
        if root_id is None:
            raise HTTPException(status_code=500, detail="You have no root folder")
        db.move_file(file_id, root_id)

    if not db.restore_file(file_id):
        raise HTTPException(status_code=404, detail="That file isn’t in the trash")
    return {"status": "ok", "message": "File restored."}


@app.post("/folders/{folder_id}/restore")
def restore_folder(folder_id: int, user_id: int = Depends(_get_current_user_id)):
    folder = db.get_folder(folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Folder not found")
    if folder["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="This folder does not belong to you")

    parent = db.get_folder(folder["parent_folder_id"]) if folder["parent_folder_id"] else None
    if parent is not None and parent["deleted_at"] is not None:
        root_id = db.get_root_folder_id(user_id)
        if root_id is not None:
            db.move_folder(folder_id, root_id)

    if not db.restore_folder(folder_id):
        raise HTTPException(status_code=404, detail="That folder isn’t in the trash")
    return {"status": "ok", "message": "Folder restored."}

@app.get("/usage")
def usage(user_id: int = Depends(_get_current_user_id)):
    return {
        "used_bytes" : storage.usage_for_user(user_id),
        "quota_bytes" : 100 * 1024 ** 3,
    }

@app.get("/search")
def search(q: str, user_id: int = Depends(_get_current_user_id)):
    term = q.strip()
    if not term:
        return {"files": []}
    return {"files": db.search_files(user_id, term)}