import sqlite3
from datetime import datetime

DB_NAME = "database.db"


def get_connection():
    return sqlite3.connect(DB_NAME)


def initialize_database():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS files (
        file_id TEXT PRIMARY KEY,
        original_name TEXT NOT NULL,
        stored_name TEXT NOT NULL,
        size INTEGER DEFAULT 0,
        status TEXT DEFAULT 'uploading',
        node TEXT,
        access_policy TEXT DEFAULT 'public',
        created_at TEXT,
        updated_at TEXT,
        download_count INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT,
        file_id TEXT,
        message TEXT,
        created_at TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS nodes (
        node_name TEXT PRIMARY KEY,
        status TEXT DEFAULT 'healthy',
        current_files INTEGER DEFAULT 0
    )
    """)

    nodes = ["node1", "node2", "node3"]

    for node in nodes:
        cursor.execute("""
        INSERT OR IGNORE INTO nodes (node_name, status, current_files)
        VALUES (?, 'healthy', 0)
        """, (node,))

    conn.commit()
    conn.close()


def create_file_record(
    file_id,
    original_name,
    stored_name,
    node,
    access_policy="public"
):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat()

    cursor.execute("""
    INSERT INTO files
    (file_id, original_name, stored_name, size, status,
    node, access_policy, created_at, updated_at, download_count)
    VALUES (?, ?, ?, 0, 'uploading', ?, ?, ?, ?, 0)
    """, (
        file_id,
        original_name,
        stored_name,
        node,
        access_policy,
        now,
        now
    ))

    conn.commit()
    conn.close()


def update_file_status(file_id, status, size=None):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.now().isoformat()

    if size is not None:
        cursor.execute("""
        UPDATE files
        SET status = ?, size = ?, updated_at = ?
        WHERE file_id = ?
        """, (status, size, now, file_id))
    else:
        cursor.execute("""
        UPDATE files
        SET status = ?, updated_at = ?
        WHERE file_id = ?
        """, (status, now, file_id))

    conn.commit()
    conn.close()


def get_file(file_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT file_id, original_name, stored_name, size,
           status, node, access_policy,
           created_at, updated_at, download_count
    FROM files
    WHERE file_id = ?
    """, (file_id,))

    row = cursor.fetchone()
    conn.close()

    if row is None:
        return None

    columns = [
        "file_id",
        "original_name",
        "stored_name",
        "size",
        "status",
        "node",
        "access_policy",
        "created_at",
        "updated_at",
        "download_count"
    ]

    return dict(zip(columns, row))


def get_all_files():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT file_id, original_name, size, status,
           node, access_policy, created_at, download_count
    FROM files
    ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()
    conn.close()

    columns = [
        "file_id",
        "original_name",
        "size",
        "status",
        "node",
        "access_policy",
        "created_at",
        "download_count"
    ]

    return [dict(zip(columns, row)) for row in rows]


def increment_download_count(file_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE files
    SET download_count = download_count + 1
    WHERE file_id = ?
    """, (file_id,))

    conn.commit()
    conn.close()


def update_node_status(node_name, status):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE nodes
    SET status = ?
    WHERE node_name = ?
    """, (status, node_name))

    conn.commit()
    conn.close()


def get_nodes():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT node_name, status, current_files
    FROM nodes
    """)

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "node_name": row[0],
            "status": row[1],
            "current_files": row[2]
        }
        for row in rows
    ]


def update_node_file_count(node_name, change):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    UPDATE nodes
    SET current_files = MAX(0, current_files + ?)
    WHERE node_name = ?
    """, (change, node_name))

    conn.commit()
    conn.close()


def save_event(event_type, file_id, message):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO events (event_type, file_id, message, created_at)
    VALUES (?, ?, ?, ?)
    """, (
        event_type,
        file_id,
        message,
        datetime.now().isoformat()
    ))

    conn.commit()
    conn.close()


def get_events():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
    SELECT id, event_type, file_id, message, created_at
    FROM events
    ORDER BY id DESC
    LIMIT 20
    """)

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "event_type": row[1],
            "file_id": row[2],
            "message": row[3],
            "created_at": row[4]
        }
        for row in rows
    ]

def delete_file_record(file_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "DELETE FROM files WHERE file_id = ?",
        (file_id,)
    )

    conn.commit()
    conn.close()