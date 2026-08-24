import os
import json
import uuid
import shutil

from storage_manager import (
    get_node_path,
    select_best_node
)

from database import (
    update_node_file_count
)


UPLOAD_FOLDER = "storage/.uploads"


def initialize_resumable_storage():

    os.makedirs(
        UPLOAD_FOLDER,
        exist_ok=True
    )


def create_upload_session(
    filename,
    total_chunks,
    access_policy="public",
    owner="guest"
):

    initialize_resumable_storage()

    upload_id = str(uuid.uuid4())

    node = select_best_node()

    if node is None:
        raise RuntimeError(
            "No healthy storage node available"
        )

    session_path = os.path.join(
        UPLOAD_FOLDER,
        upload_id
    )

    os.makedirs(
        session_path,
        exist_ok=True
    )

    session = {
        "upload_id": upload_id,
        "filename": filename,
        "total_chunks": int(total_chunks),
        "node": node,
        "access_policy": access_policy,
        "owner": owner,
        "completed_chunks": []
    }

    session_file = os.path.join(
        session_path,
        "session.json"
    )

    with open(
        session_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            session,
            file,
            indent=4
        )

    return session


def get_upload_session(upload_id):

    session_file = os.path.join(
        UPLOAD_FOLDER,
        upload_id,
        "session.json"
    )

    if not os.path.exists(session_file):
        return None

    with open(
        session_file,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


def save_upload_session(
    upload_id,
    session
):

    session_file = os.path.join(
        UPLOAD_FOLDER,
        upload_id,
        "session.json"
    )

    with open(
        session_file,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            session,
            file,
            indent=4
        )


def save_chunk(
    upload_id,
    chunk_index,
    upload_file
):

    session = get_upload_session(
        upload_id
    )

    if session is None:
        raise ValueError(
            "Upload session not found"
        )

    total_chunks = session[
        "total_chunks"
    ]

    if chunk_index < 0 or chunk_index >= total_chunks:

        raise ValueError(
            "Invalid chunk index"
        )

    session_path = os.path.join(
        UPLOAD_FOLDER,
        upload_id
    )

    chunk_path = os.path.join(
        session_path,
        f"chunk_{chunk_index:06d}"
    )

    with open(
        chunk_path,
        "wb"
    ) as output:

        shutil.copyfileobj(
            upload_file.file,
            output
        )

    if chunk_index not in session[
        "completed_chunks"
    ]:

        session[
            "completed_chunks"
        ].append(chunk_index)

        session[
            "completed_chunks"
        ].sort()

    save_upload_session(
        upload_id,
        session
    )

    return {
        "upload_id": upload_id,
        "chunk_index": chunk_index,
        "completed_chunks":
            session["completed_chunks"],
        "total_chunks":
            session["total_chunks"]
    }


def get_upload_status(upload_id):

    session = get_upload_session(
        upload_id
    )

    if session is None:
        return None

    completed = len(
        session["completed_chunks"]
    )

    total = session["total_chunks"]

    percentage = 0

    if total > 0:

        percentage = round(
            (completed / total) * 100,
            2
        )

    return {
        "upload_id": upload_id,
        "filename": session["filename"],
        "node": session["node"],
        "total_chunks": total,
        "completed_chunks":
            session["completed_chunks"],
        "completed_count": completed,
        "progress_percentage":
            percentage
    }


def complete_upload(upload_id):

    session = get_upload_session(
        upload_id
    )

    if session is None:
        raise ValueError(
            "Upload session not found"
        )

    total_chunks = session[
        "total_chunks"
    ]

    completed_chunks = session[
        "completed_chunks"
    ]

    expected_chunks = list(
        range(total_chunks)
    )

    if sorted(completed_chunks) != expected_chunks:

        raise ValueError(
            "Upload is incomplete. "
            "All chunks are required."
        )

    node = session["node"]

    filename = session["filename"]

    stored_name = (
        f"{upload_id}_{filename}"
    )

    node_path = get_node_path(
        node
    )

    final_path = os.path.join(
        node_path,
        stored_name
    )

    session_path = os.path.join(
        UPLOAD_FOLDER,
        upload_id
    )

    with open(
        final_path,
        "wb"
    ) as final_file:

        for index in range(
            total_chunks
        ):

            chunk_path = os.path.join(
                session_path,
                f"chunk_{index:06d}"
            )

            with open(
                chunk_path,
                "rb"
            ) as chunk_file:

                shutil.copyfileobj(
                    chunk_file,
                    final_file
                )

    file_size = os.path.getsize(
        final_path
    )

    update_node_file_count(
        node,
        1
    )

    shutil.rmtree(
        session_path,
        ignore_errors=True
    )

    return {
        "upload_id": upload_id,
        "filename": filename,
        "stored_name": stored_name,
        "node": node,
        "file_size": file_size,
        "access_policy": session.get("access_policy", "public"),
        "owner": session.get("owner", "guest")
    }


def cancel_upload(upload_id):

    session_path = os.path.join(
        UPLOAD_FOLDER,
        upload_id
    )

    if os.path.exists(session_path):

        shutil.rmtree(
            session_path
        )

        return True

    return False
