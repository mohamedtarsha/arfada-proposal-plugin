"""Historical winning-proposal EXEMPLAR layer (v0.6.1) — STYLE ONLY, never facts.

Learns ARFADA's human writing style, structure, formatting, and TOR→response
patterns from a local folder of past winning proposals. Strictly separated from
the factual Knowledge layer:

  CURRENT ARFADA KNOWLEDGE (Master Tracker/CVs/company/TOR/decisions) = facts
  HISTORICAL WINNING PROPOSALS                                         = style exemplars

Historical content NEVER becomes an authoritative current fact, and generation
must never copy historical text verbatim (anti-copy guard). Everything is local
and gitignored — no corpus content is committed.
"""
from .exemplar_config import get_library_root, set_library_root, clear_library_root
from .scan import scan_library
from .retrieval import retrieve_for_section, writing_dna, formatting_dna
from .anticopy import similarity_report
