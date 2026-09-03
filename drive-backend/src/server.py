from file_storage import FileStorage
from passlib.context import CryptContext
from dotenv import load_dotenv
import os

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from database import Database

load_dotenv()
app = FastAPI()
db = Database()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
storage = FileStorage(root_dir=os.getenv("STORAGE_ROOT"))
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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

    storage_name = storage.save_file(user_id, file.file)
    file_id = db.insert_file(
        user_id=user_id,
        folder_id=folder_id,
        filename=file.filename,
        file_uid=storage_name
    )
    return {
        "status": "ok",
        "message": "File uploaded.",
        "file_id": file_id,
        "filename": file.filename
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