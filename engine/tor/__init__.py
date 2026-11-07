# Arfada TOR-analysis engine — PE2-compatible, file-local, no server.
from .adapter import FileStore
from .extractor import extract_fields, extract_requirements
from .models import TORField, TORRequirement
