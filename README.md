# Sladak

An open-source similarity + AI-writing-pattern checker, modeled on how
Turnitin's two features actually work: (1) text-overlap similarity matching
against a set of sources, and (2) an AI-writing-likelihood signal. Use it to
spot-check your own writing *before* you submit it anywhere. Run it locally,
or deploy your own public copy with one click (see
[Deploying it publicly](#deploying-it-publicly)).

## Architecture

Two independent modules feed one combined report:

```
sladak/
├── extract.py     text extraction (.docx / .pdf / .txt / .md)
├── shingle.py      k-word shingling + winnowing (fingerprinting primitive)
├── compare.py      similarity module: fingerprint index + match-finding
├── filters.py      score filters: exclude quotes / exclude bibliography
├── corpus.py       persistent SQLite corpus — your own "Turnitin archive"
├── crosscheck.py   all-pairs folder comparison (collusion check)
├── ai_detect.py     AI-writing-pattern module: per-paragraph heuristic scoring
├── report.py       HTML rendering (similarity, combined, cross-check)
├── websearch.py    optional live-web spot-check (official search API only)
├── webapp.py        no-login web UI (Flask) built on the same modules
├── templates/upload.html
└── cli.py          check / report / crosscheck / corpus commands
```

`compare.py` and `ai_detect.py` don't depend on each other — `report.py` just
renders whichever results are available side by side. `cli.py report` runs
`ai_detect.py` unconditionally and `compare.py` only if you pass `--sources`
and/or `--corpus`.

## How Turnitin actually works (and where this tool differs)

Turnitin's own documentation describes the pipeline in general terms:

1. **Extract text** from the submitted file (DOCX, PDF, etc.).
2. **Fingerprint it**: break the text into overlapping word sequences and
   hash them, the same idea as `sladak/shingle.py` here.
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

Three report behaviors are also modeled directly on Turnitin's:

- **Block matching (gap bridging).** Two matches from the same source
  separated by only a few unmatched words — a copied passage with a small
  in-place edit — merge into one continuous match block, and the edited
  words count toward it, the way Turnitin highlights a lightly edited copy
  as one block. Tune with `--bridge` (default 6 words; 0 disables).
- **Original-text highlighting.** Matches are highlighted in your document's
  actual text — punctuation, capitalization, and paragraph breaks intact —
  with a numbered color badge per source, like Turnitin's document viewer.
- **Similarity bands.** The overall score is shown with Turnitin's five
  color bands: blue (no matches), green (up to 24%), yellow (25–49%),
  orange (50–74%), red (75–100%).

There's also an optional, opt-in web-spot-check mode (`--web`) that takes
your longest sentences and searches for them verbatim via the official
Google Programmable Search API — no scraping, since that violates most
search engines' terms of service. It's a coarse approximation of the "public
web" leg of a real Turnitin check, not a replacement for it.

## The AI-writing-pattern module (`ai_detect.py`)

Turnitin also ships a separate "AI Writing" feature: a proprietary classifier
that reports a percentage of the submission "likely AI-generated," with an
explicit disclaimer that it "may not always be accurate... should not be used
as the sole basis for adverse actions against a student."

This module is **not** an attempt to reproduce that classifier, and it is
**not** designed to help disguise AI-written text — its output tells you
what a naive pattern-matcher would flag, so you can go look at that passage
yourself, not so you can rewrite around the specific signals it checks.

The report headline is Turnitin-shaped: **AI-like: X% · Mixed: Y% ·
Human-like: Z%** — the share of the document's words whose paragraph falls
in each class, with a stacked color bar. Headings and blocks under 3
sentences are excluded ("not scored") instead of being counted as human.

Each paragraph is scored on fully disclosed, publicly documented heuristics,
weighted, summed, and passed through a logistic calibration:

| Signal | Weight | What it measures |
|---|---|---|
| Low sentence-length variation | 0.20 | Coefficient of variation of sentence lengths — unedited LLM output tends toward more uniform sentence length than human "bursty" writing. |
| Stock word/phrase density | 0.25 | Frequency (per 1000 words) of words and phrases LLMs statistically over-use: "moreover," "it is important to note," "delve into," "multifaceted," "landscape of," etc. |
| Connector-opened sentences | 0.20 | Fraction of sentences opening with a transition connector ("However," "Furthermore," "Additionally," …) — the signpost-every-sentence pattern. |
| Nominalization density | 0.15 | Abstract-noun density ("disruption," "fragmentation," "implications," …) — LLM formal prose is unusually nominalization-heavy. |
| Long sentences | 0.10 | Mean sentence length; LLM formal prose runs consistently long. |
| Em-dash style | 0.05 | Em dashes per 1000 words — one of the most widely reported tells of unedited LLM prose. |
| Sentence-opener repetition | 0.05 | How often sentences in a paragraph start with the same two words. |
| Paragraph-size uniformity | 0.08 (doc-level) | LLM documents tend to have eerily uniform paragraph sizes; human documents mix short and long. |

Three segmentation details matter as much as the signals:

- **Sentence splitting is abbreviation-aware** ("U.S.", "e.g.", "et al.",
  "Fig.") — a naive splitter shreds formal prose into fake short sentences,
  which makes LLM text read as bursty/human and silently breaks every
  length-based statistic.
- **Consecutive short blocks are grouped** (bullet-list items, hard-wrapped
  lines) and scored together instead of being discarded; headings stay
  separate and are never glued onto body text.
- **The references/bibliography section is excluded** from the AI analysis
  entirely — citation lists are not prose and shouldn't count either way.

Calibrated scores map to classes: **AI-like** (≥ 0.65), **mixed / unclear**
(0.40–0.65), **human-like** (< 0.40). Careful formal *human* academic writing
lands in the mixed band by design — that overlap is real, and pretending
otherwise is how false accusations happen. Every report renders a
**Limitations & false-positive warnings** section explaining this, and the
percentages here will not match Turnitin's percentage in either direction —
theirs is a trained model scoring different features.

## Install

```bash
pip install -r requirements.txt
# or: pip install -e .
```

## Usage

Combined report (similarity + AI-writing-pattern), the closest analog to a
full Turnitin submission report:

```bash
sladak report my_paper.docx --sources ./my_source_pdfs/ --out report.html
```

`--sources` is optional here — omit it to get the AI-writing-pattern
analysis alone.

Similarity-only report:

```bash
sladak check my_paper.docx --sources ./my_source_pdfs/ --out report.html
```

- `my_paper.docx` — the document you want to check (`.docx`, `.pdf`, `.txt`, `.md`).
- `--sources` — a folder of reference files to compare against (same file types).
- `--out` — where to write the HTML report (default `report.html`).

### Your own repository (`corpus`)

Turnitin's structural advantage is an archive that grows with every
submission. `corpus` gives you the same concept at personal scale — a SQLite
database you keep adding documents to (drafts, past papers, source PDFs), so
every future check runs against everything you've accumulated:

```bash
sladak corpus add old_draft.docx source1.pdf --db my_corpus.db
sladak corpus list --db my_corpus.db
sladak check new_paper.docx --corpus my_corpus.db
sladak report new_paper.docx --corpus my_corpus.db --sources ./more_pdfs/
```

`--sources` and `--corpus` can be combined; matches from the corpus are
labeled `corpus #id: name` in the report.

### Collusion check (`crosscheck`)

Compare every document in a folder against every other, both directions —
how institutions catch copying within a batch of submissions:

```bash
sladak crosscheck ./submissions/ --out crosscheck.html
```

Prints the highest-overlap pairs and writes a table report. To see the exact
matched passages for a suspicious pair, run a normal `check` on it.

### Score filters (like Turnitin's)

- `--exclude-quotes` — matched text inside quotation marks (straight or
  curly) doesn't count toward the score.
- `--exclude-bibliography` — everything after a References/Bibliography/
  Works Cited heading doesn't count.

Both work on `check` and `report`, and as checkboxes in the web UI. The
report notes which filters were active. An unclosed quotation mark is
ignored rather than silently excluding the rest of the document.

Tuning flags (all matching commands):

- `--k` (default 8) — shingle length in words. Smaller catches shorter
  matches but is noisier; larger is stricter.
- `--window` (default 4) — winnowing window; controls fingerprint density.
- `--min-run` (default 8) — minimum matched run length (in words) worth
  reporting, to filter out coincidental short phrase matches.
- `--bridge` (default 6) — join matches from the same source separated by up
  to this many words into one block, like Turnitin; 0 disables.
- `--web` (`check` only) — also spot-check your longest sentences against
  the live web. Requires `GOOGLE_CSE_API_KEY` and `GOOGLE_CSE_ENGINE_ID` env
  vars (see [Google's Programmable Search Engine docs](https://developers.google.com/custom-search/v1/overview)).

## Web UI

A no-login upload page built on the same modules: upload a file **or paste
text**, optionally attach reference sources, tick the exclude-quotes /
exclude-bibliography filters, and it returns the same combined report as
`sladak report` — overall score, per-source percentage breakdown,
highlighted matches, and the AI-writing-pattern analysis.

```bash
pip install -r requirements-web.txt
python -m sladak.webapp        # http://127.0.0.1:5000
```

What it does and doesn't do, since "no login" + "public" is a real trade-off:

- **Nothing is stored.** Each upload is written to a `tempfile.TemporaryDirectory()`
  that's deleted the instant the report is generated. No database, no
  logging of file contents, no session/account tying uploads together.
- **Request size is capped** at 20 MB (`MAX_CONTENT_LENGTH` in `webapp.py`).
- **Rate-limited per IP** (5 requests/minute, 20/hour) if `flask-limiter` is
  installed — an anonymous public endpoint that does CPU work needs this or
  it's a free DoS target.
- **The live-web spot-check is not exposed here.** It needs a paid Google API
  key; a public unauthenticated endpoint is the wrong place to spend it.

### Deploying it publicly

The fastest way to a public URL is Render's free tier — the repo ships a
`render.yaml` blueprint, so it's one click plus a free account:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/batresnja-bot/sladak)

1. Click the button (create a free [Render](https://render.com) account if
   asked — GitHub login works).
2. Approve the blueprint. Render builds the included `Dockerfile` and gives
   you a public `https://sladak-….onrender.com` URL.
3. Free-tier note: the instance sleeps when idle, so the first request after
   a quiet period takes ~30–60 seconds to wake up.

Or deploy the `Dockerfile` yourself to whatever you host things on (a VPS,
Fly.io, Railway, etc.):

```bash
docker build -t sladak .
docker run -p 8000:8000 sladak
```

Two things worth deciding *before* you put a public URL in front of this:

1. **The default rate limiter is in-process memory.** Fine for a single
   container; if you run multiple instances behind a load balancer, point
   `flask-limiter` at Redis (see its docs) or the limit won't be shared
   across instances.
2. **You are the one accepting other people's documents with no login.**
   That's fine for personal use or a small trusted group; for anything wider,
   think about whether you want stronger abuse controls (CAPTCHA, lower rate
   limits, a max file count) before the URL is public.

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
