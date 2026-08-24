import os
import hashlib
from datetime import datetime
from pymongo import MongoClient

MONGO_URI = "mongodb+srv://sk5263748_db_user:J0JgYnYVAfN2LZX9@cluster0.ny90gvb.mongodb.net/"
DB_NAME = "file_sharing_platform"

# Global client
client = MongoClient(MONGO_URI)
db = client[DB_NAME]

# Collections
files_col = db["files"]
events_col = db["events"]
nodes_col = db["nodes"]
users_col = db["users"]


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def create_user(username, password):
    if users_col.find_one({"_id": username}):
        return False

    users_col.insert_one({
        "_id": username,
        "password_hash": hash_password(password),
        "created_at": datetime.now().isoformat()
    })
    return True


def authenticate_user(username, password):
    user = users_col.find_one({"_id": username})
    if not user:
        return False
    return user["password_hash"] == hash_password(password)


def initialize_database():
    nodes = ["node1", "node2", "node3"]

    for node in nodes:
        nodes_col.update_one(
            {"_id": node},
            {
                "$setOnInsert": {
                    "status": "healthy",
                    "current_files": 0
                }
            },
            upsert=True
        )


def create_file_record(
    file_id,
    original_name,
    stored_name,
    node,
    access_policy="public",
    owner="guest"
):
    now = datetime.now().isoformat()

    files_col.insert_one({
        "_id": file_id,
        "original_name": original_name,
        "stored_name": stored_name,
        "size": 0,
        "status": "uploading",
        "node": node,
        "access_policy": access_policy,
        "owner": owner,
        "created_at": now,
        "updated_at": now,
        "download_count": 0
    })


def update_file_status(file_id, status, size=None):
    now = datetime.now().isoformat()

    update_data = {
        "status": status,
        "updated_at": now
    }

    if size is not None:
        update_data["size"] = size

    files_col.update_one(
        {"_id": file_id},
        {"$set": update_data}
    )


def get_file(file_id):
    doc = files_col.find_one({"_id": file_id})

    if doc is None:
        return None

    doc["file_id"] = doc["_id"]
    if "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


def get_all_files():
    docs = list(
        files_col.find().sort("created_at", -1)
    )

    for doc in docs:
        doc["file_id"] = doc["_id"]
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])

    return docs


def increment_download_count(file_id):
    files_col.update_one(
        {"_id": file_id},
        {"$inc": {"download_count": 1}}
    )


def update_node_status(node_name, status):
    nodes_col.update_one(
        {"_id": node_name},
        {"$set": {"status": status}}
    )


def get_nodes():
    docs = list(nodes_col.find())

    return [
        {
            "node_name": doc["_id"],
            "status": doc["status"],
            "current_files": doc["current_files"]
        }
        for doc in docs
    ]


def update_node_file_count(node_name, change):
    node = nodes_col.find_one({"_id": node_name})

    if node:
        new_count = max(
            0,
            node.get("current_files", 0) + change
        )

        nodes_col.update_one(
            {"_id": node_name},
            {"$set": {"current_files": new_count}}
        )


def save_event(event_type, file_id, message):
    events_col.insert_one({
        "event_type": event_type,
        "file_id": file_id,
        "message": message,
        "created_at": datetime.now().isoformat()
    })


def get_events():
    docs = list(
        events_col.find().sort("_id", -1).limit(20)
    )

    for doc in docs:
        doc["id"] = str(doc["_id"])
        if "_id" in doc:
            del doc["_id"]

    return docs


def delete_file_record(file_id):
    files_col.delete_one({"_id": file_id})
