"""The interactive program: asks for links in plain English, then runs the pipeline."""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from rich.console import Console

from . import config
from .condense import check_key, condense, make_client
from .download import FriendlyError, fetch, probe
from .links import instagram_id, parse_links
from .output import (categories, ensure_claude_md, folder_id, processed_ids, write_failures, write_index,
                     write_reel)

console = Console(highlight=False)

# Claude Opus 5.5 list price per million tokens (input, output). Used only for the end-of-run estimate.
PRICES = {"claude-opus-5-5": (4.00, 20.00)}
FEW_WORDS = 40   # below this many spoken words, also read the video's on-screen text


def say(text: str = "", style: str = "") -> None:
    console.print(text, style=style)


def ask(prompt: str) -> str:
    try:
        return console.input(f"[bold cyan]{prompt}[/]")
    except EOFError:
        return ""


# --------------------------------------------------------------------------- API key

def get_api_key(settings: config.Settings, interactive: bool) -> str:
    key = settings.api_key
    for attempt in range(3):
        if not key:
            if not interactive:
                raise FriendlyError("No Claude API key found. Run the program normally once, or put "
                                    "ANTHROPIC_API_KEY=... in the .env file.")
            key = prompt_for_key()
        say("Checking your API key...", "dim")
        try:
            check_key(make_client(key), settings.claude_model)
        except FriendlyError as e:
            say(str(e), "bold red")
            if not interactive or attempt == 2:
                raise
            key = ""
            continue
        if key != settings.api_key:
            config.save_api_key(key)
            say("Key works. Saved it, so you won't be asked again.", "green")
        return key
    raise FriendlyError("No working API key.")


def prompt_for_key() -> str:
    say()
    say("[bold]One-time setup: a Claude API key[/]")
    say("guruclocker uses Claude to turn each video into short action steps. That needs your own")
    say("API key (a password-like code). It costs about 8-10 cents per video, paid from your own account.")
    say()
    say("  1. Go to [underline]https://console.anthropic.com[/] and sign in (or create an account).")
    say("  2. Click [bold]Billing[/] and add a little credit ($5 covers about 50 videos).")
    say("  3. Click [bold]API Keys[/] -> [bold]Create Key[/], name it 'guruclocker', and copy it.")
    say("     It starts with [bold]sk-ant-[/].")
    say("  4. Paste it below and press Enter.")
    say("     (To paste: Ctrl+V on Windows, Cmd+V on Mac. If nothing appears, try right-clicking.)")
    say()
    while True:
        key = ask("Your API key: ").strip().strip('"').strip("'")
        if key.startswith("sk-ant-"):
            return key
        if not key:
            say("Nothing was pasted. Copy the key from the website and paste it here.", "yellow")
        else:
            say("That doesn't look like a Claude key (it should start with sk-ant-). Try again.", "yellow")


# --------------------------------------------------------------------------- links

def prompt_for_links() -> str:
    say()
    say("[bold]Paste your video links.[/] You can paste many at once: separated by commas, spaces, or")
    say("one per line. When you're done, press [bold]Enter on an empty line[/].")
    lines = []
    while True:
        line = ask("> " if not lines else "  ")
        if not line.strip():
            if lines:
                break
            continue
        lines.append(line)
    return "\n".join(lines)


# --------------------------------------------------------------------------- run

def run(link_text: str, settings: config.Settings, api_key: str, interactive: bool) -> int:
    links, junk = parse_links(link_text)
    if junk:
        say(f"Ignored text that isn't a link: {' '.join(junk)[:120]}", "dim")
    if not links:
        say("No links found in what you pasted. Links start with https://", "yellow")
        return 1

    root = settings.output_dir
    ensure_claude_md(root)
    done = processed_ids(root)
    client = make_client(api_key)
    transcriber = None
    failures: list[tuple[str, str]] = []
    made, skipped, tokens_in, tokens_out = 0, 0, 0, 0

    say(f"\nFound {len(links)} link(s). Results go to: [bold]{_show_path(root)}[/]\n")
    for i, url in enumerate(links, 1):
        tag = f"[{i}/{len(links)}]"
        ig = instagram_id(url)
        if ig and folder_id(ig) in done:
            say(f"{tag} {url}\n      already done earlier, skipping", "dim")
            skipped += 1
            continue
        say(f"{tag} {url}", "bold")
        if "instagram.com/direct/" in url:
            why = ("That's a link to an Instagram DM chat, not to the video. Open the reel itself, tap the "
                   "share (paper plane) icon -> Copy link, and use that link (it contains /reel/).")
            failures.append((url, why))
            say(f"      failed: {why}", "red")
            continue
        work = Path(tempfile.mkdtemp(prefix="guruclocker_"))
        try:
            say("      getting video details...", "dim")
            info = probe(url, settings.cookies_browser)
            if folder_id(info.video_id) in done:
                say("      already done earlier, skipping", "dim")
                skipped += 1
                continue
            say("      downloading...", "dim")
            video = fetch(url, work, settings.cookies_browser)

            if transcriber is None:
                transcriber = load_transcriber(settings)
            say("      listening (speech to text)...", "dim")
            t = transcriber(video)

            frames = []
            if len(t.text.split()) < FEW_WORDS or t.looped:
                say("      little speech found, reading the on-screen text instead...", "dim")
                from .transcribe import grab_frames
                frames = grab_frames(video, t.seconds)

            say("      summarizing with Claude...", "dim")
            c = condense(client, settings.claude_model, settings.claude_effort, info, t.text, frames, categories(root))
            tokens_in, tokens_out = tokens_in + c.input_tokens, tokens_out + c.output_tokens
            folder = write_reel(root, info, t.text, t.looped, c)
            if settings.keep_videos:
                shutil.copy2(video, folder / f"video{video.suffix}")
            done.add(folder_id(info.video_id))
            made += 1
            say(f"      done -> {folder.relative_to(root)}", "green")
        except FriendlyError as e:
            failures.append((url, str(e)))
            say(f"      failed: {e}", "red")
            if _fatal(str(e)):
                say("      This will fail for every video, so stopping here.", "red")
                break
        except Exception as e:  # unexpected: keep going with the other links
            failures.append((url, f"Unexpected error: {e}"))
            say(f"      failed (unexpected): {e}", "red")
        finally:
            shutil.rmtree(work, ignore_errors=True)

    write_index(root)
    write_failures(root, failures)
    summarize(root, settings, made, skipped, failures, tokens_in, tokens_out)
    if interactive and made:
        open_folder(root)
    return 0 if made or skipped or not failures else 2


def _fatal(message: str) -> bool:
    return any(s in message for s in ("API key", "out of credits", "isn't allowed", "doesn't exist"))


def load_transcriber(settings: config.Settings):
    from .transcribe import Transcriber

    say("      loading the speech-to-text model (the first time, this downloads 1-3 GB; later runs are quick)...",
        "dim")
    t = Transcriber(settings)
    say(f"      speech-to-text running on: {t.description}", "dim")
    return t


def summarize(root, settings, made, skipped, failures, tokens_in, tokens_out) -> None:
    say()
    say("[bold]All done.[/]")
    say(f"  {made} new video(s) processed" + (f", {skipped} skipped (done before)" if skipped else "")
        + (f", [red]{len(failures)} failed[/] (see failures.md)" if failures else ""))
    price = PRICES.get(settings.claude_model)
    if made and price:
        cost = tokens_in / 1e6 * price[0] + tokens_out / 1e6 * price[1]
        say(f"  Claude cost for this run: about ${cost:.2f} (${cost / made:.3f} per video)")
    say(f"  Your results: [bold]{_show_path(root)}[/]  (start with INDEX.md)")
    say()
    say("[bold]Next:[/] open that folder in Claude Code and say [bold]\"let's prune\"[/]. Claude will walk")
    say("you through the videos a few at a time so you can decide which ideas are worth trying.")


def _show_path(root: Path) -> str:
    # Inside Docker the real folder is the 'output' folder next to windows.bat
    return "the 'output' folder next to windows.bat" if config.IN_DOCKER else str(root)


def open_folder(root: Path) -> None:
    if config.IN_DOCKER:
        return  # windows.bat opens it after the container exits
    try:
        if platform.system() == "Darwin":
            subprocess.run(["open", str(root)], check=False)
        elif platform.system() == "Windows":
            os.startfile(root)  # type: ignore[attr-defined]
    except Exception:
        pass


# --------------------------------------------------------------------------- diagnostics

def check() -> int:
    """`--check`: print what this computer has, for troubleshooting."""
    s = config.load_settings()
    say("[bold]guruclocker system check[/]")
    say(f"  Python:         {sys.version.split()[0]} on {platform.system()} {platform.machine()}")
    say(f"  Inside Docker:  {'yes' if config.IN_DOCKER else 'no'}")
    say(f"  Output folder:  {s.output_dir}")
    say(f"  API key:        {'set (' + s.api_key[:10] + '...)' if s.api_key else 'NOT SET'}")
    say(f"  Claude model:   {s.claude_model} (effort {s.claude_effort})")
    backend = s.asr_backend if s.asr_backend != "auto" else ("mlx" if config.is_apple_silicon() else "whisper")
    say(f"  Speech-to-text: {backend}")
    if backend == "whisper":
        try:
            import ctranslate2
            n = ctranslate2.get_cuda_device_count()
            say(f"  NVIDIA GPUs:    {n} {'(fast mode)' if n else '(none found: CPU mode, slower)'}")
        except Exception as e:
            say(f"  NVIDIA GPUs:    could not check ({e})")
    from .download import FFMPEG
    say(f"  ffmpeg:         {FFMPEG}")
    return 0


# --------------------------------------------------------------------------- entry point

def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="guruclocker", description="Turn video links into transcripts + action steps.")
    p.add_argument("--links", help="links separated by commas or spaces (skips the question)")
    p.add_argument("--file", help="a text file with links (skips the question)")
    p.add_argument("--check", action="store_true", help="print a system check and exit")
    args = p.parse_args(argv)

    if args.check:
        return check()

    interactive = not (args.links or args.file) and sys.stdin.isatty()
    say("[bold]guruclocker[/]: paste video links, get the transcript + the action steps.", "")
    settings = config.load_settings()
    try:
        api_key = get_api_key(settings, interactive=sys.stdin.isatty())
        if args.file:
            text = Path(args.file).read_text(encoding="utf-8")
        elif args.links:
            text = args.links
        else:
            text = prompt_for_links()
        return run(text, settings, api_key, interactive)
    except FriendlyError as e:
        say(f"\n{e}", "bold red")
        return 1
    except KeyboardInterrupt:
        say("\nStopped. Videos that finished before you stopped are saved.", "yellow")
        return 130
