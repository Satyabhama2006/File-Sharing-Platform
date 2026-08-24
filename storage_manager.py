import os
import shutil

from database import get_nodes, update_node_file_count


BASE_STORAGE = "storage"


def initialize_storage():
    nodes = ["node1", "node2", "node3"]

    for node in nodes:
        path = os.path.join(BASE_STORAGE, node)
        os.makedirs(path, exist_ok=True)


def get_node_path(node_name):
    return os.path.join(BASE_STORAGE, node_name)


def get_healthy_nodes():
    nodes = get_nodes()

    return [
        node for node in nodes
        if node["status"] == "healthy"
    ]


def select_best_node():
    healthy_nodes = get_healthy_nodes()

    if not healthy_nodes:
        return None

    healthy_nodes.sort(
        key=lambda node: node["current_files"]
    )

    return healthy_nodes[0]["node_name"]


def save_uploaded_file(upload_file, node_name, stored_name):
    node_path = get_node_path(node_name)

    os.makedirs(node_path, exist_ok=True)

    file_path = os.path.join(
        node_path,
        stored_name
    )

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(
            upload_file.file,
            buffer
        )

    file_size = os.path.getsize(file_path)

    update_node_file_count(node_name, 1)

    return file_path, file_size


def get_file_path(node_name, stored_name):
    file_path = os.path.join(
        get_node_path(node_name),
        stored_name
    )

    if os.path.exists(file_path):
        return file_path

    return None


def get_storage_statistics():
    nodes = get_nodes()

    statistics = []

    for node in nodes:
        node_name = node["node_name"]
        node_path = get_node_path(node_name)

        total_size = 0
        total_files = 0

        if os.path.exists(node_path):
            for filename in os.listdir(node_path):

                if filename == ".gitkeep":
                    continue

                file_path = os.path.join(
                    node_path,
                    filename
                )

                if os.path.isfile(file_path):
                    total_files += 1
                    total_size += os.path.getsize(file_path)

        statistics.append({
            "node": node_name,
            "status": node["status"],
            "files": total_files,
            "size": total_size
        })

    return statistics


def check_file_availability(node_name, stored_name):
    file_path = get_file_path(
        node_name,
        stored_name
    )

    return file_path is not None

def delete_stored_file(node_name, stored_name):
    file_path = get_file_path(
        node_name,
        stored_name
    )

    if file_path is None:
        return False

    os.remove(file_path)

    update_node_file_count(
        node_name,
        -1
    )

    return True