"""Local-folder ARFADA knowledge source (v0.5.2) — OAuth-free, API-free.

A single configurable local folder is the PRIMARY knowledge source. It may be a
plain folder or a Google Drive for Desktop / OneDrive / Dropbox / network-mounted
folder — the plugin only sees a filesystem path and never calls any cloud API.

    ARFADA Knowledge/
      Projects/Master Tracker.xlsx
      Staff CVs/<Country>/*.pdf|*.docx
      Company/...
      Brand/<logo>.png

Reuses the normalized cache + snapshot machinery from gknowledge.
"""
from .local_config import get_knowledge_root, set_knowledge_root, clear_knowledge_root
from .scan import scan_local_folder
