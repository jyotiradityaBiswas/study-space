import os
import time

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = [
    "https://www.googleapis.com/auth/drive"
]

ROOT_FOLDER_ID = "1zOsOYCtlXu9C6qMyVb2X-haAtOzdj936"

_structure_cache = None
_structure_cache_time = 0
CACHE_DURATION = 60


def get_drive_service():
    private_key = os.environ["GOOGLE_PRIVATE_KEY"].replace(
        "\\n",
        "\n"
    )

    service_account_info = {
        "type": os.environ["GOOGLE_TYPE"],
        "project_id": os.environ["GOOGLE_PROJECT_ID"],
        "private_key_id": os.environ["GOOGLE_PRIVATE_KEY_ID"],
        "private_key": private_key,
        "client_email": os.environ["GOOGLE_CLIENT_EMAIL"],
        "client_id": os.environ["GOOGLE_CLIENT_ID"],
        "token_uri": os.environ["GOOGLE_TOKEN_URI"]
    }

    credentials = (
        service_account
        .Credentials
        .from_service_account_info(
            service_account_info,
            scopes=SCOPES
        )
    )

    return build(
        "drive",
        "v3",
        credentials=credentials
    )


def get_children(service, folder_id):
    query = (
        f"'{folder_id}' in parents "
        "and trashed = false"
    )

    response = service.files().list(
        q=query,
        fields="files(id, name, mimeType)",
        orderBy="name"
    ).execute()

    files = response.get("files", [])

    for file in files:
        file["url"] = (
            f"https://drive.google.com/open?id={file['id']}"
        )

    return files


def get_folder(service, folder_id):
    response = service.files().get(
        fileId=folder_id,
        fields="id, name, mimeType"
    ).execute()

    return response


def get_structure(service):
    subjects = []

    for subject in get_children(
        service,
        ROOT_FOLDER_ID
    ):
        if (
            subject["mimeType"]
            != "application/vnd.google-apps.folder"
        ):
            continue

        chapters = []

        for chapter in get_children(
            service,
            subject["id"]
        ):
            if (
                chapter["mimeType"]
                != "application/vnd.google-apps.folder"
            ):
                continue

            resources = []

            for resource in get_children(
                service,
                chapter["id"]
            ):
                resources.append({
                    "name": resource["name"],
                    "id": resource["id"],
                    "url": resource["url"]
                })

            chapters.append({
                "name": chapter["name"],
                "id": chapter["id"],
                "resources": resources
            })

        subjects.append({
            "name": subject["name"],
            "id": subject["id"],
            "chapters": chapters
        })

    return subjects


def get_cached_structure(service):
    global _structure_cache
    global _structure_cache_time

    now = time.time()

    if (
        _structure_cache is not None
        and now - _structure_cache_time < CACHE_DURATION
    ):
        return _structure_cache

    _structure_cache = get_structure(service)
    _structure_cache_time = now

    return _structure_cache


def upload_file(
    service,
    filepath,
    filename,
    folder_id
):
    metadata = {
        "name": filename,
        "parents": [folder_id]
    }

    media = MediaFileUpload(
        filepath,
        resumable=True
    )

    return service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name, mimeType, webViewLink"
    ).execute()


if __name__ == "__main__":
    service = get_drive_service()
    structure = get_structure(service)

    for subject in structure:
        print(f"\n{subject['name']}")

        for chapter in subject["chapters"]:
            print(f"  {chapter['name']}")

            for resource in chapter["resources"]:
                print(f"    - {resource['name']}")