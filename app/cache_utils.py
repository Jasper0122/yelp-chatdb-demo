# ── app/cache_utils.py  (revised) ──
"""Intent‑level cache utilities.

We cache the *canonical* (GPT‑normalized) version of a user's sentence
along with its classified intent.  Subsequent requests that hash to the
same canonical value skip the LLM call entirely.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import time
from typing import Dict, Optional

# JSONL file lives at repo‑root/intent_cache.jsonl, easy to inspect.
CACHE_FILE = pathlib.Path(__file__).resolve().parents[1] / "intent_cache.jsonl"
CACHE_FILE.touch(exist_ok=True)

# ───────────────────────────────── canonicalisation ───────────────────────────
_STOP_WORDS = {"please", "kindly", "just"}

def _canonicalize(text: str) -> str:
    """Lower‑case, strip punctuation, numbers → <NUM>, drop stop‑words."""
    text = text.lower()
    text = re.sub(r"[^\w\s]", " ", text)          # punctuation → space
    text = re.sub(r"\d+", "<NUM>", text)          # numbers → placeholder
    words = [w for w in text.split() if w not in _STOP_WORDS]
    return " ".join(words)

# ───────────────────────────────── cache helpers ──────────────────────────────

def _key(text: str) -> str:
    """Stable hash of the canonicalised sentence."""
    return hashlib.sha1(_canonicalize(text).encode()).hexdigest()


def _iter_cache():
    with open(CACHE_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                yield json.loads(line)

# Public API
# ----------

def load_from_cache(text: str) -> Optional[Dict]:
    """Return cache entry if present; else ``None``.

    Increments *hits* and *last_used* in‑memory for basic LRU stats (not
    flushed back to disk; lightweight).
    """
    k = _key(text)
    for doc in _iter_cache():
        if doc["key"] == k:
            doc["hits"] += 1
            doc["last_used"] = time.time()
            return doc
    return None


def save_to_cache(raw_text: str, canonical: str, analysis: str, intent: str) -> None:
    """Append a new JSON line to the cache file."""
    doc = {
        "key": _key(raw_text),
        "canonical": canonical,
        "analysis": analysis,
        "intent": intent,
        "hits": 1,
        "last_used": time.time(),
    }
    with open(CACHE_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(doc, ensure_ascii=False) + "\n")
