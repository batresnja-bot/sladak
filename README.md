# turnitin-diy

A local, open-source similarity + AI-writing-pattern checker, modeled on how
Turnitin's two features actually work: (1) text-overlap similarity matching
against a set of sources, and (2) an AI-writing-likelihood signal. Use it to
spot-check your own writing *before* you submit it anywhere.

## Architecture

Two independent modules feed one combined report:

```
turnitin_diy/
├── extract.py     text extraction (.docx / .pdf / .txt / .md)
├── shingle.py      k-word shingling + winnowing (fingerprinting primitive)
├── compare.py      similarity module: fingerprint index + match-finding
├── ai_detect.py     AI-writing-pattern module: per-paragraph heuristic scoring
├── report.py       HTML rendering (similarity-only, or combined)
├── websearch.py    optional live-web spot-check (official search API only)
├── webapp.py        no-login web UI (Flask) built on the same modules
├── templates/upload.html
└── cli.py          `check` (similarity only) and `report` (combined) commands
```

`compare.py` and `ai_detect.py` don't depend on each other — `report.py` just
renders whichever results are available side by side. `cli.py report` runs
`ai_detect.py` unconditionally and `compare.py` only if you pass `--sources`.

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

## The AI-writing-pattern module (`ai_detect.py`)

Turnitin also ships a separate "AI Writing" feature: a proprietary classifier
that reports a percentage of the submission "likely AI-generated," with an
explicit disclaimer that it "may not always be accurate... should not be used
as the sole basis for adverse actions against a student."

This module is **not** an attempt to reproduce that classifier, and it is
**not** designed to help disguise AI-written text — its output tells you
what a naive pattern-matcher would flag, so you can go look at that passage
yourself, not so you can rewrite around the specific signals it checks.
It scores each paragraph (0–1) on three fully disclosed, publicly documented
heuristics, weighted and summed:

| Signal | Weight | What it measures |
|---|---|---|
| Low sentence-length variation | 0.45 | Coefficient of variation of sentence lengths — unedited LLM output tends toward more uniform sentence length than human "bursty" writing. |
| Stock transition-phrase density | 0.35 | Frequency (per 1000 words) of phrases LLMs over-use: "moreover," "it is important to note," "delve into," "multifaceted," etc. |
| Sentence-opener repetition | 0.20 | How often consecutive sentences in a paragraph start with the same two words. |

Each paragraph gets a score and a confidence label (`low` / `moderate` /
`elevated` / `high`, or `insufficient text` under 3 sentences). The document
score is the paragraph scores weighted by paragraph length. Every report
renders a **Limitations & false-positive warnings** section explaining that
these signals also occur naturally in formal human writing — most notably
from non-native English writers — and that the score is a prompt to reread a
passage, never a verdict.

## Install

```bash
pip install -r requirements.txt
# or: pip install -e .
```

## Usage

Combined report (similarity + AI-writing-pattern), the closest analog to a
full Turnitin submission report:

```bash
turnitin-diy report my_paper.docx --sources ./my_source_pdfs/ --out report.html
```

`--sources` is optional here — omit it to get the AI-writing-pattern
analysis alone.

Similarity-only report:

```bash
turnitin-diy check my_paper.docx --sources ./my_source_pdfs/ --out report.html
```

- `my_paper.docx` — the document you want to check (`.docx`, `.pdf`, `.txt`, `.md`).
- `--sources` — a folder of reference files to compare against (same file types).
- `--out` — where to write the HTML report (default `report.html`).

Tuning flags (both commands):

- `--k` (default 8) — shingle length in words. Smaller catches shorter
  matches but is noisier; larger is stricter.
- `--window` (default 4) — winnowing window; controls fingerprint density.
- `--min-run` (default 8) — minimum matched run length (in words) worth
  reporting, to filter out coincidental short phrase matches.
- `--web` — also spot-check your longest sentences against the live web.
  Requires `GOOGLE_CSE_API_KEY` and `GOOGLE_CSE_ENGINE_ID` env vars (see
  [Google's Programmable Search Engine docs](https://developers.google.com/custom-search/v1/overview)).

## Web UI

A no-login upload page built on the same modules: one file input for your
document, one optional multi-file input for reference sources, and it
returns the same combined report as `turnitin-diy report`.

```bash
pip install -r requirements-web.txt
python -m turnitin_diy.webapp        # http://127.0.0.1:5000
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

This code doesn't run anywhere on its own — it's yours to deploy to whatever
you host things on (a VPS, Fly.io, Render, Railway, etc.). A `Dockerfile` is
included:

```bash
docker build -t turnitin-diy .
docker run -p 8000:8000 turnitin-diy
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
