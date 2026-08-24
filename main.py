import os
import time
import uuid

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Header
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from resumable_manager import (
    initialize_resumable_storage,
    create_upload_session,
    save_chunk,
    get_upload_status,
    complete_upload,
    cancel_upload,
)

from database import (
    initialize_database,
    create_file_record,
    update_file_status,
    get_file,
    get_all_files,
    increment_download_count,
    update_node_status,
    get_nodes,
    get_events,
    delete_file_record,
    create_user,
    authenticate_user,
)

from storage_manager import (
    initialize_storage,
    select_best_node,
    save_uploaded_file,
    get_file_path,
    get_storage_statistics,
    delete_stored_file,
)

from event_system import event_system


# --------------------------------------------------
# APPLICATION SETUP
# --------------------------------------------------

app = FastAPI(
    title="File Sharing Platform",
    description="Event-driven local cloud file sharing platform",
    version="1.0"
)


# --------------------------------------------------
# INITIALIZATION
# --------------------------------------------------

initialize_database()
initialize_storage()
initialize_resumable_storage()

app.mount(
    "/static",
    StaticFiles(directory="static"),
    name="static"
)


# --------------------------------------------------
# HOME PAGE
# --------------------------------------------------

@app.get("/")
def home():

    return FileResponse(
        "static/index.html"
    )


# --------------------------------------------------
# USER REGISTER & LOGIN
# --------------------------------------------------

@app.post("/register")
def register(
    username: str = Form(...),
    password: str = Form(...)
):
    username = username.strip()
    if not username or not password:
        raise HTTPException(
            status_code=400,
            detail="Username and password are required"
        )

    success = create_user(username, password)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Username already exists"
        )

    event_system.publish(
        "USER_REGISTERED",
        None,
        f"User '{username}' registered successfully"
    )

    return {
        "success": True,
        "message": f"User '{username}' registered successfully"
    }


@app.post("/login")
def login_endpoint(
    username: str = Form(...),
    password: str = Form(...)
):
    username = username.strip()
    success = authenticate_user(username, password)
    if not success:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password"
        )

    event_system.publish(
        "USER_LOGGED_IN",
        None,
        f"User '{username}' logged in"
    )

    return {
        "success": True,
        "message": f"User '{username}' logged in successfully",
        "username": username
    }


# --------------------------------------------------
# UPLOAD FILE
# --------------------------------------------------

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    access_policy: str = Form("public"),
    x_user: str = Header("guest")
):

    start_time = time.time()

    # Validate policy

    allowed_policies = [
        "public",
        "private",
        "read",
        "write"
    ]

    if access_policy not in allowed_policies:

        raise HTTPException(
            status_code=400,
            detail="Invalid access policy"
        )

    # Select healthy least-loaded node

    node = select_best_node()

    if node is None:

        raise HTTPException(
            status_code=503,
            detail="No healthy storage node available"
        )

    # Generate unique file ID

    file_id = str(uuid.uuid4())

    # Generate safe stored filename

    stored_name = (
        f"{file_id}_{file.filename}"
    )

    # Create database record

    create_file_record(
        file_id=file_id,
        original_name=file.filename,
        stored_name=stored_name,
        node=node,
        access_policy=access_policy,
        owner=x_user
    )

    try:

        # Save file

        file_path, file_size = save_uploaded_file(
            file,
            node,
            stored_name
        )

        # Mark upload completed

        update_file_status(
            file_id,
            "completed",
            file_size
        )

        # Generate event

        event_system.publish(
            "FILE_UPLOADED",
            file_id,
            f"{file.filename} uploaded to {node} by {x_user}"
        )

        upload_time = round(
            time.time() - start_time,
            3
        )

        return {
            "success": True,
            "message": "File uploaded successfully",
            "file_id": file_id,
            "filename": file.filename,
            "size": file_size,
            "node": node,
            "access_policy": access_policy,
            "owner": x_user,
            "upload_time_seconds": upload_time
        }

    except Exception as error:

        update_file_status(
            file_id,
            "failed"
        )

        event_system.publish(
            "UPLOAD_FAILED",
            file_id,
            str(error)
        )

        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(error)}"
        )


# --------------------------------------------------
# DOWNLOAD FILE
# --------------------------------------------------

@app.get("/download/{file_id}")
def download_file(
    file_id: str,
    x_user: str = Header("guest")
):

    file_info = get_file(file_id)

    if file_info is None:

        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    # Enforce access policy
    if file_info.get("access_policy") == "private" and file_info.get("owner") != x_user:
        raise HTTPException(
            status_code=403,
            detail="Access denied: private file"
        )

    if file_info["status"] != "completed":

        raise HTTPException(
            status_code=400,
            detail="File is not available"
        )

    file_path = get_file_path(
        file_info["node"],
        file_info["stored_name"]
    )

    if file_path is None:

        raise HTTPException(
            status_code=404,
            detail="Physical file not found"
        )

    increment_download_count(
        file_id
    )

    event_system.publish(
        "FILE_DOWNLOADED",
        file_id,
        f"{file_info['original_name']} downloaded by {x_user}"
    )

    return FileResponse(
        file_path,
        filename=file_info["original_name"],
        media_type="application/octet-stream"
    )


# --------------------------------------------------
# LIST ALL FILES
# --------------------------------------------------

@app.get("/files")
def list_files(x_user: str = Header("guest")):

    all_files = get_all_files()
    filtered = []

    for f in all_files:
        if f.get("access_policy") == "private":
            if f.get("owner") == x_user:
                filtered.append(f)
        else:
            filtered.append(f)

    return {
        "files": filtered
    }


# --------------------------------------------------
# GET SINGLE FILE INFORMATION
# --------------------------------------------------

@app.get("/files/{file_id}")
def file_information(
    file_id: str,
    x_user: str = Header("guest")
):

    file_info = get_file(
        file_id
    )

    if file_info is None:

        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    # Enforce access policy
    if file_info.get("access_policy") == "private" and file_info.get("owner") != x_user:
        raise HTTPException(
            status_code=403,
            detail="Access denied: private file"
        )

    return file_info


# --------------------------------------------------
# STORAGE STATUS
# --------------------------------------------------

@app.get("/storage/status")
def storage_status():

    return {
        "nodes": get_nodes(),
        "storage": get_storage_statistics()
    }


# --------------------------------------------------
# SERVER FAILURE SIMULATION
# --------------------------------------------------

@app.post("/nodes/{node_name}/fail")
def fail_node(node_name: str):

    valid_nodes = [
        "node1",
        "node2",
        "node3"
    ]

    if node_name not in valid_nodes:

        raise HTTPException(
            status_code=404,
            detail="Node not found"
        )

    update_node_status(
        node_name,
        "failed"
    )

    event_system.publish(
        "NODE_FAILED",
        None,
        f"{node_name} marked as failed"
    )

    return {
        "success": True,
        "node": node_name,
        "status": "failed"
    }


# --------------------------------------------------
# SERVER RECOVERY
# --------------------------------------------------

@app.post("/nodes/{node_name}/recover")
def recover_node(node_name: str):

    valid_nodes = [
        "node1",
        "node2",
        "node3"
    ]

    if node_name not in valid_nodes:

        raise HTTPException(
            status_code=404,
            detail="Node not found"
        )

    update_node_status(
        node_name,
        "healthy"
    )

    event_system.publish(
        "NODE_RECOVERED",
        None,
        f"{node_name} recovered"
    )

    return {
        "success": True,
        "node": node_name,
        "status": "healthy"
    }


# --------------------------------------------------
# EVENTS
# --------------------------------------------------

@app.get("/events")
def events():

    return {
        "events": get_events()
    }


# --------------------------------------------------
# PERFORMANCE INFORMATION
# --------------------------------------------------

@app.get("/performance")
def performance():

    files = get_all_files()

    total_files = len(files)

    total_downloads = sum(
        file.get("download_count", 0)
        for file in files
    )

    total_size = sum(
        file.get("size", 0)
        for file in files
    )

    completed_files = sum(
        1
        for file in files
        if file.get("status") == "completed"
    )

    failed_files = sum(
        1
        for file in files
        if file.get("status") == "failed"
    )

    return {
        "total_files": total_files,
        "completed_files": completed_files,
        "failed_files": failed_files,
        "total_downloads": total_downloads,
        "total_storage_bytes": total_size
    }


# --------------------------------------------------
# DELETE FILE
# --------------------------------------------------

@app.delete("/files/{file_id}")
def delete_file(
    file_id: str,
    x_user: str = Header("guest")
):

    file_info = get_file(
        file_id
    )

    if file_info is None:

        raise HTTPException(
            status_code=404,
            detail="File not found"
        )

    # Restrict delete: only the owner can delete
    owner = file_info.get("owner", "guest")
    if owner != "guest" and owner != x_user:
        raise HTTPException(
            status_code=403,
            detail="Access denied: only the owner can delete this file"
        )

    deleted = delete_stored_file(
        file_info["node"],
        file_info["stored_name"]
    )

    if not deleted:

        raise HTTPException(
            status_code=404,
            detail="Physical file not found"
        )

    delete_file_record(
        file_id
    )

    event_system.publish(
        "FILE_DELETED",
        file_id,
        f"{file_info['original_name']} deleted by {x_user}"
    )

    return {
        "success": True,
        "message": "File deleted successfully",
        "filename": file_info["original_name"],
        "node": file_info["node"]
    }


# ==================================================
# RESUMABLE / CHUNKED UPLOAD
# ==================================================


# --------------------------------------------------
# START RESUMABLE UPLOAD
# --------------------------------------------------

@app.post("/resumable/start")
def start_resumable_upload(
    filename: str = Form(...),
    total_chunks: int = Form(...),
    access_policy: str = Form("public"),
    x_user: str = Header("guest")
):

    if total_chunks <= 0:

        raise HTTPException(
            status_code=400,
            detail="total_chunks must be greater than 0"
        )

    allowed_policies = [
        "public",
        "private",
        "read",
        "write"
    ]

    if access_policy not in allowed_policies:

        raise HTTPException(
            status_code=400,
            detail="Invalid access policy"
        )

    try:

        session = create_upload_session(
            filename,
            total_chunks,
            access_policy=access_policy,
            owner=x_user
        )

        event_system.publish(
            "UPLOAD_STARTED",
            session["upload_id"],
            f"Resumable upload started: {filename} by {x_user}"
        )

        return {
            "success": True,
            "upload_id": session["upload_id"],
            "filename": filename,
            "total_chunks": total_chunks,
            "node": session["node"]
        }

    except Exception as error:

        raise HTTPException(
            status_code=503,
            detail=str(error)
        )


# --------------------------------------------------
# UPLOAD ONE CHUNK
# --------------------------------------------------

@app.post(
    "/resumable/{upload_id}/chunk/{chunk_index}"
)
async def upload_chunk(
    upload_id: str,
    chunk_index: int,
    file: UploadFile = File(...)
):

    try:

        result = save_chunk(
            upload_id,
            chunk_index,
            file
        )

        return {
            "success": True,
            **result
        }

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# --------------------------------------------------
# CHECK RESUMABLE UPLOAD STATUS
# --------------------------------------------------

@app.get(
    "/resumable/{upload_id}/status"
)
def resumable_upload_status(
    upload_id: str
):

    status = get_upload_status(
        upload_id
    )

    if status is None:

        raise HTTPException(
            status_code=404,
            detail="Upload session not found"
        )

    return status


# --------------------------------------------------
# COMPLETE RESUMABLE UPLOAD
# --------------------------------------------------

@app.post(
    "/resumable/{upload_id}/complete"
)
def finish_resumable_upload(
    upload_id: str
):

    try:

        result = complete_upload(
            upload_id
        )

        file_id = str(
            uuid.uuid4()
        )

        stored_name = result[
            "stored_name"
        ]

        create_file_record(
            file_id=file_id,
            original_name=result["filename"],
            stored_name=stored_name,
            node=result["node"],
            access_policy=result["access_policy"],
            owner=result["owner"]
        )

        update_file_status(
            file_id,
            "completed",
            result["file_size"]
        )

        event_system.publish(
            "FILE_UPLOADED",
            file_id,
            f"Resumable upload completed: "
            f"{result['filename']} by {result['owner']}"
        )

        return {
            "success": True,
            "message": "Resumable upload completed",
            "file_id": file_id,
            **result
        }

    except ValueError as error:

        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    except Exception as error:

        raise HTTPException(
            status_code=500,
            detail=str(error)
        )


# --------------------------------------------------
# CANCEL RESUMABLE UPLOAD
# --------------------------------------------------

@app.delete(
    "/resumable/{upload_id}"
)
def cancel_resumable_upload(
    upload_id: str
):

    deleted = cancel_upload(
        upload_id
    )

    if not deleted:

        raise HTTPException(
            status_code=404,
            detail="Upload session not found"
        )

    event_system.publish(
        "UPLOAD_CANCELLED",
        upload_id,
        "Resumable upload cancelled"
    )

    return {
        "success": True,
        "message": "Resumable upload cancelled"
    }
