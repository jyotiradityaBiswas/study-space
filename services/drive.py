import os
import time

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = [
    "https://www.googleapis.com/auth/drive"
]

ROOT_FOLDER_ID = "1zOsOYCtlXu9C6qMyVb2X-haAtOzdj936"
PENDING_UPLOAD_FOLDER_ID = "12Yocq__wvs_Reavq7OHyx0vZZCU30Vbk"

_structure_cache = None
_structure_cache_time = 0
CACHE_DURATION = 60


def get_drive_service():

    credentials = None

    refresh_token = os.environ.get(
        "GOOGLE_REFRESH_TOKEN"
    )

    client_id = os.environ.get(
        "GOOGLE_CLIENT_ID"
    )

    client_secret = os.environ.get(
        "GOOGLE_CLIENT_SECRET"
    )

    if not refresh_token:
        raise RuntimeError(
            "GOOGLE_REFRESH_TOKEN is not configured."
        )

    if not client_id:
        raise RuntimeError(
            "GOOGLE_CLIENT_ID is not configured."
        )

    if not client_secret:
        raise RuntimeError(
            "GOOGLE_CLIENT_SECRET is not configured."
        )

    credentials = Credentials(
        token=None,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=SCOPES
    )

    if credentials.expired:
        credentials.refresh(
            Request()
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

    files = response.get(
        "files",
        []
    )

    for file in files:

        file["url"] = (
            f"https://drive.google.com/open?id="
            f"{file['id']}"
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

    _structure_cache = get_structure(
        service
    )

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


def upload_pending_file(
    service,
    filepath,
    filename
):
    metadata = {
        "name": filename,
        "parents": [PENDING_UPLOAD_FOLDER_ID]
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