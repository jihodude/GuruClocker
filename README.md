# guruclocker

You saved a bunch of videos (Instagram reels, TikToks, Shorts) where someone pitches an idea: a side hustle, a real-estate trick, a sales script, a scholarship hack. guruclocker turns each one into something you can actually judge:

- **the full transcript**, so you don't have to rewatch it
- **a condensed version**: the bottom line, concrete action steps, what it really costs (money, time, risk), what to check before acting, and any red flags (DM funnels, paid courses, sponsors)

Everything lands in one `output` folder, sorted into topic folders. Then you open that folder in Claude Code and go through the ideas together, keeping the good ones and archiving the rest.

```
output/
  INDEX.md                      <- every video, one line each. Start here.
  CLAUDE.md                     <- tells Claude Code how to help you prune
  real-estate/
    dscr-loan-142k-house__demdzjjomrp/
      link.md                   <- the link, the creator, the caption
      transcript.txt            <- everything said in the video
      condensed.md              <- bottom line, action steps, cost, red flags
  sales/
    ...
```

**Cost:** turning speech into text happens on your own computer, for free. The condensing uses Claude, through your own API key: about **8-10 cents per video** ($5 of credit covers about 50 videos).

---

## Windows

### First time (about 15 minutes, mostly waiting)

1. **Get the code.** On the GitHub page, click the green **Code** button, then **Download ZIP**. Open your Downloads folder, right-click the ZIP, choose **Extract All...**, and pick somewhere easy to find, such as your Desktop.
2. **Open the extracted folder and double-click `windows.bat`.**
   - If Windows shows a blue box saying "Windows protected your PC", click **More info**, then **Run anyway**. (It shows that for any downloaded script.)
3. **The first time, it sets itself up.**
   - It installs a small tool called **uv**, which then installs Python and everything else guruclocker needs.
   - Everything goes inside your user folder and the guruclocker folder; nothing else on your PC changes, and you don't need admin rights.
   - This takes 5-10 minutes and downloads about 3 GB. Text will scroll by; that's normal.
4. **It asks for your Claude API key** (only the first time):
   - Go to **https://console.anthropic.com** and make an account.
   - Click **Billing** and add $5 of credit.
   - Click **API Keys**, then **Create Key**. Copy the key (it starts with `sk-ant-`).
   - Click into the black window and paste with **Ctrl+V** (or right-click), then press **Enter**.
5. **Paste your video links**, separated by commas or one per line, then press **Enter on an empty line**.

When it finishes, the `output` folder opens by itself.

**Graphics card:** if your PC has an NVIDIA graphics card, guruclocker uses it automatically ("fast mode"). If it doesn't have one, or the card doesn't work with it, guruclocker uses the processor instead. That's slower (roughly 15-45 seconds per minute of video) but works fine.

### Every time after that

Double-click `windows.bat`, paste links, and press Enter twice.

---

## Mac

1. **Get the code** (GitHub: **Code** -> **Download ZIP**, then double-click the ZIP to unzip it), or `git clone` it.
2. **Double-click `mac.command`.**
   - The first time, macOS may say it "cannot be opened because it is from an unidentified developer". Close that message, **right-click** `mac.command`, choose **Open**, then click **Open** again. You only do this once.
   - If it says you don't have permission, open the Terminal app, type `bash ` (with a space), drag `mac.command` into the Terminal window, and press Enter.
3. The first run installs everything it needs (a few minutes), then asks for your Claude API key (same steps as Windows, step 4) and your links.

On Apple Silicon Macs (M1-M4), speech-to-text runs on the Mac's own chip and is fast. Intel Macs use the slower processor mode.

---

## Then: prune with Claude Code

1. Open the `output` folder in Claude Code (the desktop app: **Open folder**; or run `claude` inside the folder in a terminal).
2. Say **"let's prune"**.

Claude goes through your videos 3 at a time. For each one it shows what the idea is, the smallest experiment you could run, what it costs, and a suggested ROI score with its honest call. **You decide** keep or prune:

- **Kept** ideas move to `output/refined/<category>/`, with a note on why you kept them.
- **Pruned** ideas move to `output/_archive/roi-<score>__...`. Nothing is ever deleted, and the note says why you cut it.

Run guruclocker again any time with new links. Videos it has already done (including ones you archived or kept) are skipped, so you're never charged twice for the same video.

---

## Troubleshooting

**"That's a link to an Instagram DM chat"**
You copied the address of a DM conversation (`instagram.com/direct/...`). Open the reel itself, tap the share (paper plane) icon -> **Copy link**, and paste that instead. Good links contain `/reel/` or `/p/`.

**"Instagram keeps blocking me" / "The site blocked the download"**
Instagram sometimes refuses downloads from people who aren't logged in, especially when you run a lot in a row. Wait an hour and try again; links that failed are listed in `output/failures.md`. You can also borrow your browser's Instagram login: open `app/.env` in Notepad or TextEdit and set `COOKIES_BROWSER=chrome` (or `safari`, `firefox`, `edge`). You must be logged into Instagram in that browser.

**"Your Anthropic account is out of credits"**
Add credit at console.anthropic.com -> Billing, then run it again. Videos that already finished are kept.

**"Your Claude API key didn't work"**
Open `app/.env` in Notepad or TextEdit, delete everything after `ANTHROPIC_API_KEY=` on that line, save, and run it again. It will ask for the key again.

**Windows: the window closes instantly or nothing happens**
You may have run it from inside the ZIP. Right-click the ZIP -> **Extract All...** first, then double-click `windows.bat` in the extracted folder.

**Windows: "Couldn't install uv"**
Usually a network or antivirus block. Try again on a home network. If your antivirus quarantined something, allow `uv.exe`.

**Check what guruclocker sees on your computer**
Windows: open the folder, click the address bar, type `cmd`, and press Enter. Then type `windows.bat --check` and press Enter. Mac: `bash mac.command --check`. This shows the API key status, whether an NVIDIA GPU was found, and where results go. Send a screenshot of it if you ask someone for help.

### Settings (`app/.env`)

The `.env` file inside the `app` folder (open it with Notepad or TextEdit; on a Mac, press **Cmd+Shift+.** in Finder to show hidden files) holds your API key and a few optional settings, each explained inside: which Claude model to use, the speech-to-text model, and whether to keep the downloaded videos (`KEEP_VIDEOS=true`).

---

## For developers

The friend-facing top folder holds only the launchers and this README; everything else is in `app/`. Developer commands go through `app/Makefile`. Run them from the repo root as `make -C app <command>`, or `cd app` first (`make -C app` lists them). Results always go to the top-level `output/`.

| Command | What it does |
|---|---|
| `make setup` | Install uv + dependencies natively (Mac/Linux), create `.env` |
| `make run` | Run natively; `make run LINKS="url, url"` or `make run FILE=links.txt` skips the prompt |
| `make check` | System check (GPU, models, key, paths) |
| `make test` | Unit tests (Claude calls are mocked) |
| `make docker-build` / `make docker-run` | Optional: build / run in Docker instead (GPU auto-detected). Handy on Linux servers or for Docker practice |
| `make docker-check` / `make docker-clean` | System check inside Docker / remove image + cached model |

**How it works:** links -> `yt-dlp` download -> 16 kHz audio (bundled ffmpeg via `imageio-ffmpeg`) -> speech-to-text -> one Claude call per video (`claude-opus-5-5`, adaptive thinking, JSON schema output) -> files.

| Where it runs | Speech-to-text |
|---|---|
| Apple Silicon Mac (native) | MLX `Qwen3-ASR-1.7B-8bit`, transcribed in 30 s chunks, with a guard against the model getting stuck repeating itself |
| Windows / Linux with an NVIDIA GPU | faster-whisper `large-v3-turbo`, float16 (falls back to CPU if the GPU libraries fail) |
| Everything else (no NVIDIA GPU, Intel Mac) | faster-whisper `small`, int8 |

If a video has little speech (under 40 words), 8 evenly spaced frames go to Claude along with the transcript, so videos made of on-screen text lists still get read.

**Layout:** `app/guruclocker/wizard.py` (prompts and plain-English messages), `download.py`, `transcribe.py`, `condense.py` (+ `prompts/condense.md`), `output.py` (+ `templates/CLAUDE.md`), `config.py`. Both launchers use [uv](https://docs.astral.sh/uv/) to install Python 3.11 and the locked dependencies (`uv.lock`) into `.venv`. On 64-bit Windows/Linux, the CUDA 12 cuBLAS/cuDNN 9 libraries come from pip wheels (cuBLAS is capped below 12.9.3, the first version without a Windows wheel), so the PC only needs an NVIDIA driver; `transcribe.py` adds their DLL folders on Windows. The optional Docker image is `python:3.11-slim` + uv.

Developer files live in `app/dev/`: `PRD.md` (requirements and decisions), `Dockerfile`, and `tests/`.
