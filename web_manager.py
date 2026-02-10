import os
import glob
import asyncio
from typing import Optional
from fastapi import FastAPI, HTTPException, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from telethon import TelegramClient, functions, types
import uvicorn
import config
import shutil

app = FastAPI()

# CORS configuration - allow all origins for Railway deployment
origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (photos)
os.makedirs("static/photos", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Proxy logic (reused)
async def get_client(session_path: str):
    """Create and connect a client for a specific session file, trying proxies in order."""
    if not config.PROXY_LIST:
        # Try without proxy? Or fail? The previous code implied proxy was required if list existed.
        # If empty list, passing None to proxy usually works for direct connection.
        client = TelegramClient(session_path, config.API_ID, config.API_HASH)
        await client.connect()
        return client

    last_exc = None
    for proxy_conf in config.PROXY_LIST:
        try:
            client = TelegramClient(
                session_path,
                config.API_ID,
                config.API_HASH,
                proxy=proxy_conf
            )
            await client.connect()
            return client
        except Exception as e:
            last_exc = e
            # Try next proxy
            pass
            
    raise Exception(f"Failed to connect with any proxy. Last error: {last_exc}")

class SessionUpdate(BaseModel):
    session_file: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    about: Optional[str] = None

@app.get("/api/folders")
async def list_folders():
    """List all folders in SESSIONS_DIR"""
    folders = []
    if os.path.exists(config.SESSIONS_DIR):
        for item in os.listdir(config.SESSIONS_DIR):
            item_path = os.path.join(config.SESSIONS_DIR, item)
            if os.path.isdir(item_path):
                # Count session files in this folder
                session_count = len([f for f in os.listdir(item_path) if f.endswith('.session')])
                folders.append({
                    "name": item,
                    "session_count": session_count
                })
    folders.sort(key=lambda x: x['name'])
    return folders

@app.get("/api/sessions")
async def list_sessions(folder: str = None):
    """List all session files in SESSIONS_DIR, optionally filtered by folder"""
    sessions = []
    
    # Determine which directory to scan
    if folder:
        scan_dir = os.path.join(config.SESSIONS_DIR, folder)
    else:
        scan_dir = config.SESSIONS_DIR
    
    if not os.path.exists(scan_dir):
        return sessions
    
    for root, dirs, files in os.walk(scan_dir):
        for file in files:
            if file.endswith(".session"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, config.SESSIONS_DIR)
                sessions.append({
                    "path": rel_path,
                    "name": file,
                    "folder": os.path.dirname(rel_path)
                })
    
    # Sort by folder then name
    sessions.sort(key=lambda x: (x['folder'], x['name']))
    return sessions

@app.post("/api/session/scan")
async def scan_session(data: dict):
    """Connect to session and get user info"""
    rel_path = data.get("path")
    if not rel_path:
        raise HTTPException(status_code=400, detail="Path required")
        
    full_path = os.path.join(config.SESSIONS_DIR, rel_path)
    
    # Telethon client init takes path w/o extension usually
    session_path_no_ext = os.path.splitext(full_path)[0]
    
    client = await get_client(session_path_no_ext)
    
    try:
        if not await client.is_user_authorized():
            await client.disconnect()
            return {"status": "unauthorized"}
            
        me = await client.get_me()
        
        # Download profile photo
        photo_path = f"static/photos/{me.id}.jpg"
        # Always re-download to be fresh? Or check exist? Let's check exist for speed.
        if not os.path.exists(photo_path):
            await client.download_profile_photo(me, file=photo_path)
            
        # Get full info for About (Bio)
        full_user = await client(functions.users.GetFullUserRequest(me))
        about = full_user.full_user.about
            
        info = {
            "status": "authorized",
            "id": me.id,
            "username": me.username,
            "first_name": me.first_name,
            "last_name": me.last_name,
            "phone": me.phone,
            "about": about,
            # Return absolute URL or relative to backend
            "photo": f"http://127.0.0.1:8000/{photo_path}" if os.path.exists(photo_path) else None
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    finally:
        await client.disconnect()
        
    return info

@app.post("/api/session/update")
async def update_session(
    session_path: str = Form(...),
    first_name: str = Form(None),
    last_name: str = Form(None),
    username: str = Form(None),
    about: str = Form(None),
    file: UploadFile = File(None)
):
    full_path = os.path.join(config.SESSIONS_DIR, session_path)
    session_path_no_ext = os.path.splitext(full_path)[0]
    
    client = await get_client(session_path_no_ext)
    
    try:
        if not await client.is_user_authorized():
            raise HTTPException(status_code=401, detail="Session unauthorized")
            
        # Update Profile (Name/About)
        if first_name is not None or last_name is not None or about is not None:
             await client(functions.account.UpdateProfileRequest(
                 first_name=first_name if first_name else "",
                 last_name=last_name if last_name else "", 
                 about=about if about else ""
             ))
             
        # Update Username
        if username is not None:
            # Check if username changed? Or just try update
            # Error if username taken
            try:
                await client(functions.account.UpdateUsernameRequest(username=username))
            except Exception as e:
                # If username invalid or taken
                return JSONResponse(status_code=400, content={"status": "error", "message": f"Username error: {str(e)}"})
            
        # Update Profile Photo
        if file:
            # Save temp file
            temp_filename = f"temp_{file.filename}"
            with open(temp_filename, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            # Upload
            uploaded = await client.upload_file(temp_filename)
            await client(functions.photos.UploadProfilePhotoRequest(file=uploaded))
            
            # Cleanup
            os.remove(temp_filename)
            
        return {"status": "success", "message": "Updated successfully"}
        
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})
    finally:
        await client.disconnect()

if __name__ == "__main__":
    uvicorn.run("web_manager:app", host="127.0.0.1", port=8000, reload=True)
