# guruclocker: PRD (v1)

*v1, 2026-11-16. Built; see README.md for usage.*

## 1. Problem

People save short videos (Instagram reels and similar) that pitch money, career or productivity ideas. Watching them again to work out what is actually being claimed, what it would cost to try, and whether it's a funnel takes a lot of time.

We ran this process by hand on 21 reels:

1. download
2. transcribe
3. condense into action steps
4. prune on ROI with Claude

About half of the reels were funnels or low-ROI ideas. guruclocker automates steps 1–3 and sets up step 4.

## 2. Users

| User | Machine | Terminal skill |
|---|---|---|
| Jiho (author) | Apple Silicon Mac (M4) | Comfortable |
| Friend (first outside user) | Windows; GPU unknown | **None**. Every step must be in plain English. |

## 3. Goals / non-goals

**Goals**
- **Start by double-clicking a file:**
  - `windows.bat` on Windows
  - `mac.command` on Mac
- **The program guides the user in plain English:**
  - what to install
  - where to paste links
  - where to get an API key
  - what went wrong
- **Paste links → get an organized output folder:**
  - folders are named by category
  - each reel folder holds a link, the full transcript and a condensed version
- **The output folder works as a Claude Code workspace:** open it, and Claude runs the pruning conversation the way we did by hand.
- **Transcription is free and runs on the user's machine:**
  - fast on an Apple Silicon Mac or an NVIDIA GPU
  - slower but working on CPU-only machines

**Non-goals (v1)**
- Web UI or localhost page. Input is in the terminal only.
- Automated judging or pruning. Pruning stays human, done with Claude Code.
- Hosting, accounts, multiple users, Kubernetes.
- Labels like DO IT / SKEPTIC (rejected).

## 4. User flow

### First run
1. Get the code: GitHub → **Code → Download ZIP** → unzip (or `git clone`).
2. Double-click the launcher:
   - **Windows:** `windows.bat`
   - **Mac:** `mac.command` (first time: right-click → Open, because macOS blocks downloaded scripts)
3. The launcher checks requirements and explains how to fix anything missing:
   - **Windows:** "Docker Desktop isn't installed. I'm opening the download page. Install it, restart your PC, then double-click `windows.bat` again."
   - **Mac:** installs `uv` and `ffmpeg` if missing, with an explanation of each.
4. **API key setup:** "guruclocker uses Claude to summarize videos. You need your own API key from console.anthropic.com (it costs a few cents per video). Paste it here and press Enter." The program checks that the key works, then saves it to `.env`.
5. Model setup, shown once: "Downloading the speech-to-text model (about 1.5–3 GB, one time only)…"

### Every run
1. Double-click the launcher.
2. "Paste your links (separate them with commas or new lines). Press Enter on an empty line when you're done."
3. Progress for each link, in plain words:
   ```
   [3/12] instagram.com/reel/DemDzjjOmRp
          downloading… transcribing… summarizing… done → real-estate/dscr-loan-142k-house__demdzjjomrp
   ```
4. Summary: "Done: 11 videos processed, 1 failed (Instagram blocked it; try again later). Your results are in the `output` folder." The output folder then opens in Explorer or Finder.
5. "Next: open the `output` folder in Claude Code and say *let's prune*."

## 5. Output (the contract)

```
output/
  CLAUDE.md                          ← pruning instructions for Claude Code (written once)
  INDEX.md                           ← every reel: category, title, bottom line (rebuilt each run)
  failures.md                        ← links that failed and why
  <category>/                        ← e.g. real-estate, sales; chosen by Claude
    <topic-slug>__<reelID>/
      link.md                        ← URL, creator, date, views/likes, caption
      transcript.txt                 ← full transcript (+ on-screen text section if used)
      condensed.md                   ← see below
```

**`condensed.md` format** (same as the manual round, without labels):
- **Bottom line:** 1–2 sentences: what's true, what's the hook.
- **Action steps:** numbered and concrete. What you would actually do to try it.
- **Real cost:** money / time / risk.
- **Verify before acting:** the claims to check.
- **Red flags** (if any): funnel ("comment X"), sponsor, income claims, legal issues.

**Categories:**
- Claude picks a short kebab-case category for each reel.
- It is shown the existing folder names and reuses one when it fits, so folders don't split into near-duplicates.

**Re-running:**
- The same `output/` folder keeps growing.
- Reels that were already processed (matched by reel ID) are skipped.
- Folders that Claude Code moved into `_archive/` or `refined/` count as processed and are never recreated.

**Videos:** deleted after transcription by default. Set `KEEP_VIDEOS=true` in `.env` to keep them.

### `output/CLAUDE.md` (the pruning workflow)
This file tells a Claude Code session to:
1. Go through about 3 reels per batch. Show each reel's bottom line, the experiment, its cost, and a suggested ROI score (1–5) with a short "My call."
2. Wait for the user's keep/prune decision. Never decide on its own.
3. **Prune:** add a `## Pruned (date) — ROI N/5` note with the reason, then move the folder to `_archive/roi-N__<category>__<folder>`. Never delete.
4. **Keep:** add a `## Kept (date)` note with the user's reasoning, then move the folder to `refined/<category>/`. Related reels can be merged on request.
5. Keep cost and judgment calls on a strong model, and do a web lookup when a claim needs fact-checking.
6. Rebuild `refined/INDEX.md` at the end.

## 6. Architecture

```
launcher (windows.bat / mac.command)
   └─► guruclocker wizard (Python, interactive, plain English)
         for each link:
           download   yt-dlp (anonymous; optional browser cookies)
           audio      ffmpeg → 16 kHz mono wav
           transcribe backend auto-selected (below), 30s chunks, loop guard
           condense   Claude API (anthropic SDK) → category, slug, title, condensed.md
                      if transcript is nearly empty → also send ~8 frames (vision)
           write      output/<category>/<slug>__<id>/{link.md, transcript.txt, condensed.md}
```

**Transcription backends (auto-selected):**

| Machine | Path | Backend | Speed (1-min reel) |
|---|---|---|---|
| Apple Silicon Mac | native (`mac.command` → uv venv) | MLX Qwen3-ASR-1.7B-8bit (round-1 winner) | ~10 s |
| Windows + NVIDIA | Docker, `--gpus all` | faster-whisper `large-v3-turbo`, CUDA | a few s |
| Windows without NVIDIA / other | Docker, CPU | faster-whisper `small`, int8 | ~15–45 s |

- **GPU detection:** `windows.bat` runs `nvidia-smi`. If it succeeds, it starts the container with the GPU and says "NVIDIA GPU found, using fast mode." Otherwise it says "No NVIDIA GPU found, using CPU mode (slower, still works)."
- **Overrides:** both the backend and the model can be changed in `.env`.

**Condensing:**
- One call to `claude-opus-5-5` per reel, with adaptive thinking and structured JSON output (category, slug, title, markdown body).
- The model can be changed in `.env` (`CLAUDE_MODEL`).
- Judgment stays on a strong model by default.

**Packaging:**
- **`Makefile`** (for the developer):
  - `make help` / `make setup` / `make run` / `make test` / `make clean`
  - `make docker-build` / `make docker-run`
  - The launchers call the same steps underneath.
- **`Dockerfile`:** one image.
  - Python 3.11-slim + ffmpeg + faster-whisper.
  - On amd64, the CUDA runtime libraries (pip `nvidia-cublas-cu12`, `nvidia-cudnn-cu12`) are added so the GPU works.
  - Code is copied in.
  - `output/` and `.env` are mounted from the host.
  - The model cache lives in a named volume, so it downloads once.
- **No docker-compose:** the launchers and the Makefile call `docker run` directly. One container doesn't need compose.
- **`.env.example`:**
  - `ANTHROPIC_API_KEY`
  - `CLAUDE_MODEL`
  - `ASR_BACKEND=auto`
  - `WHISPER_MODEL`
  - `KEEP_VIDEOS=false`
  - `COOKIES_BROWSER=`
- **`README.md`:** plain-English install steps for Windows and Mac with screenshots-in-words, cost note, FAQ (Instagram blocks, "Windows protected your PC", "unidentified developer" on Mac), and developer section (make targets).

**Repo layout**
```
guruclocker/
  windows.bat   mac.command   Makefile   Dockerfile   .dockerignore
  pyproject.toml   uv.lock   .env.example   .gitignore   README.md   PRD.md
  guruclocker/  __main__.py  wizard.py  download.py  transcribe.py  condense.py
                output.py  prompts/condense.md  templates/CLAUDE.md
  tests/        (unit tests for link parsing, slugging, loop guard, output layout,
                 skip-already-processed; condense mocked)
  output/       (gitignored)
```

The round-1 prototype (`Exploration/guruclocker/docs/guruclocker.py`) supplied the download, chunked-MLX and loop-guard code. Its `compare` (ASR A/B) command was not carried over in v1; the model choice it produced (Qwen3-ASR 1.7B) is baked in.

## 7. Error handling (plain English, never a stack trace by default)

| Situation | Message (gist) |
|---|---|
| Docker not installed / not running | "Docker Desktop isn't running. Open it from the Start menu, wait for the whale icon to settle, then try again." |
| Bad or missing API key | "That key didn't work. Copy it again from console.anthropic.com → API Keys." |
| Out of API credits | "Your Anthropic account is out of credits. Add some at console.anthropic.com → Billing." |
| Instagram blocks a download | Logged to `failures.md`; "Instagram blocked this one. Try again later, or set COOKIES_BROWSER (see README)." |
| Not a video link | "That doesn't look like a video link. Skipped." |
| Private/deleted reel | "This reel is private or deleted. Skipped." |
| Transcript looped/empty | Falls back to on-screen frames. If both are empty: "No speech or readable text found." |

A full log goes to `output/.logs/` for debugging.

## 8. Testing / acceptance

**Will be verified before handoff (on the M4 Mac):**
1. `make test` passes.
2. `mac.command` run from scratch on 3 real reels (including one on-screen-text reel) produces the correct folder layout, sensible categories and good condensed files.
3. Running again with an already-processed link skips it, and a mix of good and bad links is handled.
4. `make docker-build && make docker-run` on the Mac (Docker CPU path, arm64) processes 1–2 reels with identical output layout.
5. Opening `output/` in Claude Code and saying "let's prune" starts the batch-of-3 workflow.
6. Cost per reel is measured and written into the README.

**Can't be verified here (needs the friend):**
- `windows.bat` on real Windows.
- The NVIDIA GPU path.
- The image's amd64 build. I'll cross-build the amd64 image to confirm it at least builds.
- The README will include a short "first run checklist" so his first run doubles as the test.

**Done when:** all 6 local checks pass, the repo is committed locally, and the README walks a non-technical Windows user from zero to a finished `output/` folder.

## 9. Decisions log

| Decision | Choice |
|---|---|
| Repo location | `~/Documents/Programming/guruclocker` |
| Sharing | Private GitHub repo. Jiho pushes; the friend downloads the ZIP or clones. |
| Launchers | `windows.bat` (Docker) and `mac.command` (native MLX), named after their OS |
| Input | Terminal only, interactive, plain English |
| Categories | Auto from content, reusing existing folder names |
| Condense model | `claude-opus-5-5` (configurable) |
| Videos | Deleted after transcription (configurable) |
| API key | Each user uses their own, entered on first run and saved to `.env` |
| Kubernetes | No |

## 10. Risks

- **The Windows/GPU path is untested until the friend runs it.** Mitigations: CPU fallback, clear diagnostics, and a `windows.bat --check` that prints what it detected.
- **Instagram may start blocking anonymous downloads.** The browser-cookie option is documented.
- **Docker Desktop on Windows requires WSL2 and virtualization enabled in BIOS.** The README covers it. It's the biggest setup hurdle for a beginner.
- **macOS Gatekeeper blocks `mac.command` from a ZIP.** The right-click → Open step is documented.
- **API cost** is borne by each user. The README states the per-reel cost.
