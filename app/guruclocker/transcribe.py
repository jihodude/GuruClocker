"""Speech-to-text, run on this computer for free.

Apple Silicon Mac  -> MLX Qwen3-ASR-1.7B (chosen in round-1 testing over 0.6B for accuracy)
NVIDIA GPU         -> faster-whisper large-v3-turbo on CUDA
anything else      -> faster-whisper small on CPU (slower, still fine for short reels)
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

from .config import MLX_MODEL, Settings, is_apple_silicon
from .download import FFMPEG

LOOP_NOTE = "[guruclocker: the speech model got stuck repeating itself here (music or sound effects).]"


def extract_audio(video: Path, wav: Path) -> float:
    """Video -> 16 kHz mono WAV. Returns the audio length in seconds."""
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000", str(wav)],
        check=True,
    )
    with wave.open(str(wav)) as w:
        return w.getnframes() / float(w.getframerate())


def collapse_loops(text: str, max_repeats: int = 8) -> tuple[str, bool]:
    """Speech models can loop on music ('Oh. Oh. Oh. ...' x4000). Collapse any 1-6 word phrase that
    repeats more than max_repeats times in a row, and report whether that happened."""
    pattern = re.compile(r"((?:\S+\s+){1,6}?)\1{%d,}" % max_repeats)
    collapsed = pattern.sub(lambda m: m.group(1) + "[...repeated...] ", text + " ").strip()
    return collapsed, collapsed != text.strip()


@dataclass
class Transcript:
    text: str
    looped: bool
    seconds: float


class _MLX:
    def __init__(self) -> None:
        from mlx_audio.stt.utils import load_model

        self.model = load_model(MLX_MODEL)
        self.description = "Apple Silicon (MLX, Qwen3-ASR 1.7B)"

    def __call__(self, wav: Path) -> str:
        try:
            # 30s chunks: if the model loops on a music section, only that chunk is affected
            result = self.model.generate(str(wav), chunk_duration=30.0)
        except TypeError:
            result = self.model.generate(str(wav))
        return result.text.strip()


def _windows_gpu_libraries() -> None:
    """On Windows, the NVIDIA libraries installed by pip live in site-packages/nvidia/*/bin, where
    Windows doesn't look for DLLs by default. Point it there before ctranslate2 loads them."""
    if sys.platform != "win32":
        return
    for base in map(Path, sys.path):
        nvidia = base / "nvidia"
        if not nvidia.is_dir():
            continue
        for bin_dir in nvidia.glob("*/bin"):
            os.add_dll_directory(str(bin_dir))
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")


class _Whisper:
    def __init__(self, model_name: str, device: str) -> None:
        _windows_gpu_libraries()
        import ctranslate2

        if device == "auto":
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        self.requested_model = model_name
        try:
            self._load(device)
        except Exception:
            if device != "cuda":
                raise
            self._load("cpu")  # GPU libraries missing or broken: still work, just slower

    def _load(self, device: str) -> None:
        from faster_whisper import WhisperModel

        name = self.requested_model or ("large-v3-turbo" if device == "cuda" else "small")
        self.model = WhisperModel(name, device=device, compute_type="float16" if device == "cuda" else "int8")
        self.device = device
        self.description = (f"NVIDIA GPU (Whisper {name})" if device == "cuda"
                            else f"processor (Whisper {name}; slower, but works)")

    def __call__(self, wav: Path) -> str:
        try:
            return self._transcribe(wav)
        except Exception:
            # A missing GPU library often only shows up on first use. Switch to the processor and retry once.
            if self.device != "cuda":
                raise
            self._load("cpu")
            print("      (the graphics card didn't work, so switched to processor mode)")
            return self._transcribe(wav)

    def _transcribe(self, wav: Path) -> str:
        # vad_filter skips music/silence, which also prevents the looping problem
        segments, _ = self.model.transcribe(str(wav), vad_filter=True, beam_size=5)
        return " ".join(s.text.strip() for s in segments).strip()


class Transcriber:
    """Loads the speech model once, then transcribes videos one by one."""

    def __init__(self, settings: Settings) -> None:
        backend = settings.asr_backend
        if backend == "auto":
            backend = "mlx" if is_apple_silicon() else "whisper"
        self._impl = _MLX() if backend == "mlx" else _Whisper(settings.whisper_model, settings.whisper_device)
        self.description = self._impl.description

    def __call__(self, video: Path) -> Transcript:
        wav = video.with_name("_audio.wav")
        try:
            try:
                seconds = extract_audio(video, wav)
            except subprocess.CalledProcessError:  # video has no sound track
                return Transcript(text="", looped=False, seconds=video_duration(video))
            text, looped = collapse_loops(self._impl(wav)) if seconds > 0.5 else ("", False)
            return Transcript(text=text, looped=looped, seconds=seconds)
        finally:
            wav.unlink(missing_ok=True)


def video_duration(video: Path) -> float:
    """Length in seconds, read from ffmpeg's banner (no ffprobe needed)."""
    out = subprocess.run([FFMPEG, "-hide_banner", "-i", str(video)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", out)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 30.0


def grab_frames(video: Path, seconds: float, count: int = 8) -> list[Path]:
    """Evenly spaced still images, for videos whose message is on-screen text rather than speech."""
    out_dir = video.parent / "_frames"
    out_dir.mkdir(exist_ok=True)
    fps = count / max(seconds, 1.0)
    subprocess.run(
        [FFMPEG, "-y", "-loglevel", "error", "-i", str(video), "-vf", f"fps={fps:.4f},scale=768:-2",
         "-frames:v", str(count), "-q:v", "4", str(out_dir / "f%02d.jpg")],
        check=True,
    )
    return sorted(out_dir.glob("f*.jpg"))
