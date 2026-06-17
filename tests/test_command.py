import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.command import AgyCommand


def _build(**kw):
    base = dict(query="hi", directory="/proj", timeout=120)
    base.update(kw)
    return AgyCommand(**base).build()


def test_build_minimal():
    c = _build()
    assert c[0] == "agy"
    assert "--print" in c and "hi" in c
    assert "--add-dir" in c and "/proj" in c
    # print-timeout alignment is on by default
    assert "--print-timeout" in c
    assert "120s" in c


def test_build_print_timeout_aligns_to_timeout():
    c = _build(timeout=45)
    assert "--print-timeout" in c
    i = c.index("--print-timeout")
    assert c[i + 1] == "45s"


def test_build_align_print_timeout_disabled():
    c = _build(align_print_timeout=False)
    assert "--print-timeout" not in c


def test_build_model():
    c = _build(model="gemini-3.5-flash")
    assert "--model" in c
    i = c.index("--model")
    assert c[i + 1] == "gemini-3.5-flash"


def test_build_extra_dirs_repeatable():
    c = _build(add_dirs=("/a", "/b"))
    # working dir + two extra dirs => three --add-dir occurrences
    assert c.count("--add-dir") == 3
    assert "/a" in c and "/b" in c


def test_build_skip_permissions():
    c = _build(skip_permissions=True)
    assert "--dangerously-skip-permissions" in c


def test_build_sandbox():
    c = _build(sandbox=True)
    assert "--sandbox" in c


def test_build_continue_last():
    c = _build(continue_last=True)
    assert "--continue" in c


def test_build_conversation_id():
    c = _build(conversation_id="abc-123")
    assert "--conversation" in c
    i = c.index("--conversation")
    assert c[i + 1] == "abc-123"


def test_build_conversation_id_takes_precedence_over_continue():
    c = _build(conversation_id="abc-123", continue_last=True)
    assert "--conversation" in c
    assert "--continue" not in c


def test_build_query_is_last_argument():
    c = _build(query="special query")
    assert c[-2] == "--print"
    assert c[-1] == "special query"
