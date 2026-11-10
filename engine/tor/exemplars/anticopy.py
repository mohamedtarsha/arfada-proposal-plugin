"""Deterministic anti-copy similarity guard (v0.6.1).

Compares generated section text against the historical exemplar excerpts that were
provided to generation. Flags substantial verbatim copying while ignoring generic
proposal terminology (short shared phrases, standard headings).

Method: shared 8-gram (word) overlap ratio + longest shared run. Conservative
thresholds to avoid penalizing unavoidable terminology.
"""
from __future__ import annotations

import re

_STOP = {"the", "a", "an", "of", "to", "and", "in", "for", "with", "will", "be",
         "is", "are", "on", "by", "as", "that", "this", "which", "shall"}

_NGRAM = 8
_OVERLAP_THRESHOLD = 0.18   # >=18% of generated 8-grams appear verbatim in exemplar
_RUN_THRESHOLD = 14          # a shared verbatim run of >=14 words


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def _ngrams(tokens: list[str], n: int) -> set:
    return {" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)}


def _longest_shared_run(a: list[str], b: list[str]) -> int:
    bset = set(" ".join(b[i:i + 4]) for i in range(len(b) - 3))  # index 4-grams of b
    best = 0
    i = 0
    while i < len(a) - 3:
        if " ".join(a[i:i + 4]) in bset:
            # extend
            run = 4
            while i + run < len(a):
                frag = " ".join(a[i + run - 3:i + run + 1])
                if frag in bset:
                    run += 1
                else:
                    break
            best = max(best, run)
            i += run
        else:
            i += 1
    return best


def similarity_report(generated: str, exemplar_excerpts: list[str]) -> dict:
    """Return {max_overlap, longest_run, flagged, detail}. Deterministic."""
    gen_tokens = [t for t in _tokens(generated)]
    gen_ngrams = _ngrams(gen_tokens, _NGRAM)
    if not gen_ngrams:
        return {"max_overlap": 0.0, "longest_run": 0, "flagged": False, "detail": "too short"}

    max_overlap = 0.0
    longest_run = 0
    worst = ""
    for ex in exemplar_excerpts or []:
        ex_tokens = _tokens(ex)
        ex_ngrams = _ngrams(ex_tokens, _NGRAM)
        if not ex_ngrams:
            continue
        shared = gen_ngrams & ex_ngrams
        overlap = len(shared) / max(1, len(gen_ngrams))
        run = _longest_shared_run(gen_tokens, ex_tokens)
        if overlap > max_overlap:
            max_overlap = overlap
        if run > longest_run:
            longest_run = run
            worst = ex[:60]

    flagged = (max_overlap >= _OVERLAP_THRESHOLD) or (longest_run >= _RUN_THRESHOLD)
    return {
        "max_overlap": round(max_overlap, 3),
        "longest_run": longest_run,
        "flagged": flagged,
        "detail": (f"Substantial verbatim similarity to a historical exemplar "
                   f"(overlap {max_overlap:.0%}, run {longest_run} words). Rewrite in "
                   f"ARFADA's style without copying." if flagged else "within acceptable range"),
    }


def leaked_historical_entities(text: str, exemplar_meta: list[dict]) -> list[str]:
    """Detect old client/project tokens from historical metadata appearing in new text.

    Splits each project-folder name into tokens and flags DISTINCTIVE ones
    (uppercase acronyms >=3 chars, or digit-led project codes) that appear in the
    generated text. Generic words are not flagged.
    """
    low = (text or "").lower()
    hits = []
    for e in exemplar_meta or []:
        folder = (e.get("project_folder") or "")
        for tok in re.split(r"[\s_\-]+", folder):
            if not tok:
                continue
            distinctive = (re.fullmatch(r"[A-Z]{3,}", tok)            # acronym (IRC, NRC, SCI)
                           or re.fullmatch(r"\d{2,4}", tok)           # project code (261)
                           or re.match(r"\d{2,4}[A-Za-z]", tok))      # 261Eval
            if distinctive and len(tok) >= 3 and tok.lower() in low:
                hits.append(tok)
    return sorted(set(hits))
