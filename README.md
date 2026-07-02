# turnitin-diy

A local, open-source text-similarity checker. It implements the same core
technique that Turnitin, iThenticate, and MOSS are built on — k-word
shingling plus winnowing fingerprint matching — so you can spot-check your
own writing for unattributed overlap *before* you submit it anywhere.

## How Turnitin actually works (and where this tool differs)

Turnitin's own documentation describes the pipeline in general terms:

1. **Extract text** from the submitted file (DOCX, PDF, etc.).
2. **Fingerprint it**: break the text into overlapping word sequences and
   hash them, the same idea as `turnitin_diy/shingle.py` here.
3. **Compare fingerprints against three indexes**:
   - the current and archived public web,
   - a private repository of papers previously submitted by students at
     subscribing institutions,
   - licensed publisher/journal content.
4. **Report a Similarity Score** — the percentage of the submission that
   matches *something* in those indexes — broken down source-by-source, with
   the overlapping text highlighted.

Turnitin is explicit that this score is **not a plagiarism verdict**. Quoted
material, properly cited paraphrases, bibliographies, and common phrases all
show up as "matches." A human (usually the instructor) is expected to open
the report and judge whether each match is a citation, a coincidence, or a
real problem.

**What this tool cannot replicate**: it has no access to Turnitin's private
student-paper archive or its licensed publisher content, and no proprietary
paraphrase-detection model. So a percentage from this tool will never equal
a percentage from real Turnitin — it's not trying to.

**What this tool does the same way Turnitin does it**: the actual matching
algorithm. Give it a folder of reference documents — your own earlier
drafts, the PDFs of the sources you cited, classmates' papers you have
permission to check against, whatever you want to compare against — and it
will find and highlight overlapping passages exactly the way a similarity
report does, using the technique described in Schleimer, Wilkerson & Aiken's
["Winnowing: Local Algorithms for Document Fingerprinting"](https://theory.stanford.edu/~aiken/publications/papers/sigmod03.pdf)
(SIGMOD 2003) — the paper the whole plagiarism-detection industry, including
MOSS, traces back to.

There's also an optional, opt-in web-spot-check mode (`--web`) that takes
your longest sentences and searches for them verbatim via the official
Google Programmable Search API — no scraping, since that violates most
search engines' terms of service. It's a coarse approximation of the "public
web" leg of a real Turnitin check, not a replacement for it.

## Install

```bash
pip install -r requirements.txt
# or: pip install -e .
```

## Usage

```bash
turnitin-diy check my_paper.docx --sources ./my_source_pdfs/ --out report.html
```

- `my_paper.docx` — the document you want to check (`.docx`, `.pdf`, `.txt`, `.md`).
- `--sources` — a folder of reference files to compare against (same file types).
- `--out` — where to write the HTML report (default `report.html`). Open it
  in a browser: matched passages are highlighted and color-coded by source,
  with an overall overlap percentage at the top, similar to a Turnitin
  Similarity Report.

Tuning flags:

- `--k` (default 8) — shingle length in words. Smaller catches shorter
  matches but is noisier; larger is stricter.
- `--window` (default 4) — winnowing window; controls fingerprint density.
- `--min-run` (default 8) — minimum matched run length (in words) worth
  reporting, to filter out coincidental short phrase matches.
- `--web` — also spot-check your longest sentences against the live web.
  Requires `GOOGLE_CSE_API_KEY` and `GOOGLE_CSE_ENGINE_ID` env vars (see
  [Google's Programmable Search Engine docs](https://developers.google.com/custom-search/v1/overview)).

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Intended use

This is meant to help you catch accidental unattributed overlap in your own
writing before you submit it — the same reason universities let students run
draft Similarity Reports themselves. It is not intended to help disguise
copied text; the highlighting shows you exactly what a real similarity
checker would flag so you can go fix the citation or the phrasing, not so
you can dodge detection.
