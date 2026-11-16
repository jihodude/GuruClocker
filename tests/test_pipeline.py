import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from guruclocker import config, condense, output
from guruclocker.download import FriendlyError, VideoInfo, explain
from guruclocker.links import clean, instagram_id, parse_links
from guruclocker.transcribe import collapse_loops

INFO = VideoInfo(url="https://www.instagram.com/reel/DemDzjjOmRp/", video_id="DemDzjjOmRp", title="t",
                 uploader="someone", upload_date="2026-11-01", view_count=12000, like_count=300,
                 caption="Comment LOAN and I'll DM you")


def make_condensed(**kw):
    base = dict(category="Real Estate", slug="DSCR Loan: $142k house!", title="DSCR loan on a $142k house",
                bottom_line="Real loan, rosy rent.", onscreen_text="", body="## What the video says\n- x")
    base.update(kw)
    return condense.Condensed(**base)


# --------------------------------------------------------------------------- links

def test_parse_links_mixed_separators_and_junk():
    text = ("https://www.instagram.com/reel/DemDzjjOmRp/?srtk=abc==, https://www.instagram.com/reel/Dcbn5zUIvY2/"
            "?mdxt=x9 ft 10.11 in\nreal estate https://www.instagram.com/reel/DemDzjjOmRp/ https://youtu.be/abc")
    links, junk = parse_links(text)
    assert links == ["https://www.instagram.com/reel/DemDzjjOmRp/", "https://www.instagram.com/reel/Dcbn5zUIvY2/",
                     "https://youtu.be/abc"]
    assert "real" in junk and "estate" in junk


def test_instagram_variants():
    assert instagram_id("https://instagram.com/p/AbC_1-2/") == "AbC_1-2"
    assert instagram_id("https://www.instagram.com/someuser/reel/XYZ/?igsh=1") == "XYZ"
    assert clean("https://www.instagram.com/reels/XYZ/?igsh=1") == "https://www.instagram.com/reel/XYZ/"
    assert instagram_id("https://example.com/video") is None


# --------------------------------------------------------------------------- transcribe helpers

def test_collapse_loops():
    text, looped = collapse_loops("intro " + "Oh. " * 50 + "then real words")
    assert looped and text.count("Oh.") <= 2 and "real words" in text
    assert collapse_loops("a normal sentence")[1] is False


# --------------------------------------------------------------------------- output folder

def test_write_reel_layout(tmp_path):
    folder = output.write_reel(tmp_path, INFO, "hello world", False, make_condensed())
    assert folder == tmp_path / "real-estate" / "dscr-loan-142k-house__demdzjjomrp"
    assert sorted(p.name for p in folder.iterdir()) == ["condensed.md", "link.md", "transcript.txt"]
    assert "**Bottom line:** Real loan, rosy rent." in (folder / "condensed.md").read_text()
    assert "Comment LOAN" in (folder / "link.md").read_text()
    assert "12,000 views" in (folder / "link.md").read_text()


def test_onscreen_text_and_loop_note_go_in_transcript(tmp_path):
    folder = output.write_reel(tmp_path, INFO, "", True, make_condensed(onscreen_text="HomePath\nRentometer"))
    t = (folder / "transcript.txt").read_text()
    assert "stuck repeating" in t and "(no speech detected)" in t and "Rentometer" in t


def test_processed_ids_include_archive_and_refined(tmp_path):
    (tmp_path / "sales" / "seven-laws__dfc8sq-gj-y").mkdir(parents=True)
    (tmp_path / "_archive" / "roi-1__ai__roblox__dfdte4qomfo").mkdir(parents=True)
    (tmp_path / "refined" / "real-estate" / "dscr__demdzjjomrp" / "tools" / "stack__dfxfxhroiy5").mkdir(parents=True)
    assert output.processed_ids(tmp_path) >= {"dfc8sq-gj-y", "dfdte4qomfo", "demdzjjomrp", "dfxfxhroiy5"}
    assert output.categories(tmp_path) == ["sales"]


def test_index_and_claude_md(tmp_path):
    output.write_reel(tmp_path, INFO, "x", False, make_condensed())
    output.write_index(tmp_path)
    index = (tmp_path / "INDEX.md").read_text()
    assert "## real-estate" in index and "Real loan, rosy rent." in index and INFO.url in index
    output.ensure_claude_md(tmp_path)
    assert "let's prune" in (tmp_path / "CLAUDE.md").read_text()


def test_failures_append(tmp_path):
    output.write_failures(tmp_path, [("https://a", "private")])
    output.write_failures(tmp_path, [("https://b", "blocked")])
    text = (tmp_path / "failures.md").read_text()
    assert text.count("# Links that failed") == 1 and "https://a" in text and "https://b" in text


# --------------------------------------------------------------------------- condense (Claude mocked)

class FakeMessages:
    def __init__(self, payload, stop="end_turn"):
        self.payload, self.stop, self.kwargs = payload, stop, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        return SimpleNamespace(stop_reason=self.stop, content=[SimpleNamespace(type="text", text=json.dumps(self.payload))],
                               usage=SimpleNamespace(input_tokens=1000, output_tokens=500))


def fake_client(payload, stop="end_turn"):
    msgs = FakeMessages(payload, stop)
    return SimpleNamespace(beta=SimpleNamespace(messages=msgs)), msgs


def test_condense_request_and_parse(tmp_path):
    frame = tmp_path / "f01.jpg"
    frame.write_bytes(b"\xff\xd8fake")
    payload = {k: "v" for k in condense.SCHEMA["required"]}
    client, msgs = fake_client(payload)
    c = condense.condense(client, "claude-opus-5-5", "high", INFO, "transcript here", [frame], ["sales"])
    assert c.title == "v" and c.input_tokens == 1000
    kw = msgs.kwargs
    assert kw["model"] == "claude-opus-5-5"
    assert kw["thinking"] == {"type": "adaptive"}
    assert kw["output_config"]["format"]["type"] == "json_schema"
    content = kw["messages"][0]["content"]
    assert content[0]["type"] == "image" and "Existing categories: sales" in content[-1]["text"]
    assert "Comment LOAN" in content[-1]["text"] and "transcript here" in content[-1]["text"]


def test_condense_refusal_is_friendly():
    client, _ = fake_client({}, stop="refusal")
    with pytest.raises(FriendlyError):
        condense.condense(client, "m", "high", INFO, "t", [], [])


# --------------------------------------------------------------------------- config / errors

def test_save_api_key_in_place(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("# note\nANTHROPIC_API_KEY=\nKEEP_VIDEOS=false\n")
    monkeypatch.setattr(config, "ENV_FILE", env)
    config.save_api_key("sk-ant-test")
    assert env.read_text() == "# note\nANTHROPIC_API_KEY=sk-ant-test\nKEEP_VIDEOS=false\n"


def test_download_errors_are_plain_english():
    assert "private" in explain(Exception("ERROR: This content is private"))
    assert "blocked" in explain(Exception("ERROR: login required, use --cookies"))
