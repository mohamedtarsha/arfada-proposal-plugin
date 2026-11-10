"""Google Drive + Sheets clients (read-only), with an injectable protocol.

Real clients wrap google-api-python-client. Tests inject a fake implementing the
same small interface, so the whole connector is testable with NO credentials.

Interface:
    DriveLike.list_folder(folder_id) -> list[{id,name,mimeType,modifiedTime,size,parents}]
    DriveLike.download(file_id) -> bytes
    SheetsLike.read(spreadsheet_id, sheet_name) -> list[list[str]]  (rows of cells)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Protocol

_DEPS = Path(__file__).resolve().parent.parent.parent.parent / ".mcp_deps"
if _DEPS.exists() and str(_DEPS) not in sys.path:
    sys.path.insert(0, str(_DEPS))


class DriveLike(Protocol):
    def list_folder(self, folder_id: str) -> list[dict]: ...
    def download(self, file_id: str) -> bytes: ...


class SheetsLike(Protocol):
    def read(self, spreadsheet_id: str, sheet_name: str) -> list[list]: ...


# ---------------------------------------------------------------------------
# Real implementations (used by the CLI scripts with live OAuth creds)
# ---------------------------------------------------------------------------

class DriveClient:
    def __init__(self, creds):
        from googleapiclient.discovery import build
        self._svc = build("drive", "v3", credentials=creds, cache_discovery=False)

    def list_folder(self, folder_id: str) -> list[dict]:
        out: list[dict] = []
        page_token = None
        q = f"'{folder_id}' in parents and trashed=false"
        while True:
            resp = self._svc.files().list(
                q=q, spaces="drive",
                fields="nextPageToken, files(id,name,mimeType,modifiedTime,size,parents)",
                pageToken=page_token, pageSize=200,
            ).execute()
            out.extend(resp.get("files", []))
            page_token = resp.get("nextPageToken")
            if not page_token:
                break
        return out

    def download(self, file_id: str) -> bytes:
        from googleapiclient.http import MediaIoBaseDownload
        import io
        req = self._svc.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, req)
        done = False
        while not done:
            _status, done = downloader.next_chunk()
        return buf.getvalue()


class SheetsClient:
    def __init__(self, creds):
        from googleapiclient.discovery import build
        self._svc = build("sheets", "v4", credentials=creds, cache_discovery=False)

    def read(self, spreadsheet_id: str, sheet_name: str) -> list[list]:
        rng = sheet_name if sheet_name else "A:ZZ"
        resp = self._svc.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id, range=rng,
        ).execute()
        return resp.get("values", [])
