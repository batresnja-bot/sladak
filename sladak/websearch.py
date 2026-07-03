"""Optional web-source checking, via official search APIs only (no scraping).

A real Turnitin check compares against a live web index plus a private
archive of previously submitted student papers and licensed publisher
content -- none of which is available outside Turnitin. The closest a DIY
tool can legitimately get is: pick a handful of suspicious sentences from
your own document and search for them verbatim via a search API you hold a
key for, then eyeball the results yourself.

This module intentionally does NOT scrape search engines (against most
providers' terms of service). It calls the Google Programmable Search
Engine JSON API, which requires your own API key + engine ID.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import requests

GOOGLE_CSE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"


@dataclass
class WebHit:
    query: str
    title: str
    url: str
    snippet: str


def pick_candidate_sentences(text: str, count: int = 15, min_words: int = 12) -> list[str]:
    """Heuristic: longer sentences are more useful/specific web queries."""
    import re

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    candidates = [s.strip() for s in sentences if len(s.split()) >= min_words]
    candidates.sort(key=lambda s: len(s.split()), reverse=True)
    return candidates[:count]


def search_google_cse(query: str, api_key: str, engine_id: str) -> list[WebHit]:
    params = {"key": api_key, "cx": engine_id, "q": f'"{query}"'}
    resp = requests.get(GOOGLE_CSE_ENDPOINT, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    hits = []
    for item in data.get("items", []):
        hits.append(
            WebHit(
                query=query,
                title=item.get("title", ""),
                url=item.get("link", ""),
                snippet=item.get("snippet", ""),
            )
        )
    return hits


def check_web(text: str, count: int = 15) -> list[WebHit]:
    api_key = os.environ.get("GOOGLE_CSE_API_KEY")
    engine_id = os.environ.get("GOOGLE_CSE_ENGINE_ID")
    if not api_key or not engine_id:
        raise RuntimeError(
            "Set GOOGLE_CSE_API_KEY and GOOGLE_CSE_ENGINE_ID to enable web checking "
            "(https://developers.google.com/custom-search/v1/overview)."
        )
    all_hits: list[WebHit] = []
    for sentence in pick_candidate_sentences(text, count=count):
        try:
            all_hits.extend(search_google_cse(sentence, api_key, engine_id))
        except requests.RequestException as exc:
            print(f"  web search failed for one sentence: {exc}")
    return all_hits
