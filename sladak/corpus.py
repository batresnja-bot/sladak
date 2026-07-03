"""A persistent local corpus -- your own version of Turnitin's repository.

Turnitin's biggest structural advantage is an archive that grows with every
submission. This module gives you the same concept at personal scale: a
SQLite database you add documents to over time (your drafts, past papers,
source PDFs), so every future check runs against everything you've
accumulated without re-pointing at folders.

Raw text is stored rather than fingerprints so the corpus stays valid if
you later check with different k/window settings.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .compare import Source, build_source
from .shingle import tokenize

DEFAULT_DB = Path("turnitin_corpus.db")


@dataclass
class CorpusDoc:
    id: int
    name: str
    n_words: int
    added_at: str


class Corpus:
    def __init__(self, path: Path = DEFAULT_DB):
        self.path = Path(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS docs ("
            " id INTEGER PRIMARY KEY,"
            " name TEXT NOT NULL,"
            " text TEXT NOT NULL,"
            " added_at TEXT NOT NULL)"
        )
        self.conn.commit()

    def add(self, name: str, text: str) -> int:
        added_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        cur = self.conn.execute(
            "INSERT INTO docs (name, text, added_at) VALUES (?, ?, ?)", (name, text, added_at)
        )
        self.conn.commit()
        return cur.lastrowid

    def documents(self) -> list[CorpusDoc]:
        rows = self.conn.execute("SELECT id, name, text, added_at FROM docs ORDER BY id").fetchall()
        return [CorpusDoc(id=r[0], name=r[1], n_words=len(tokenize(r[2])), added_at=r[3]) for r in rows]

    def remove(self, doc_id: int) -> bool:
        cur = self.conn.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
        self.conn.commit()
        return cur.rowcount > 0

    def build_sources(self, k: int = 8, window: int = 4) -> list[Source]:
        rows = self.conn.execute("SELECT id, name, text FROM docs ORDER BY id").fetchall()
        return [build_source(f"corpus #{r[0]}: {r[1]}", r[2], k=k, window=window) for r in rows]

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Corpus":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
