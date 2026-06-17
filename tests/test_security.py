import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_resolve_within_root_ok(tmp_path):
    from src.security import resolve_within_root

    (tmp_path / "sub").mkdir()
    f = tmp_path / "sub" / "a.py"
    f.write_text("x")
    abs_p, rel_p = resolve_within_root(str(tmp_path), "sub/a.py")
    assert abs_p == f.resolve()
    assert rel_p == Path("sub/a.py")


def test_resolve_within_root_absolute(tmp_path):
    from src.security import resolve_within_root

    f = tmp_path / "a.py"
    f.write_text("x")
    abs_p, rel_p = resolve_within_root(str(tmp_path), str(f))
    assert abs_p == f.resolve()
    assert rel_p == Path("a.py")


def test_resolve_rejects_escape(tmp_path):
    from src.security import SecurityError, resolve_within_root

    with pytest.raises(SecurityError):
        resolve_within_root(str(tmp_path), "../../etc/passwd")


def test_resolve_rejects_absolute_outside(tmp_path):
    from src.security import SecurityError, resolve_within_root

    with pytest.raises(SecurityError):
        resolve_within_root(str(tmp_path), "/etc/passwd")


def test_allowed_dirs_empty_allows_all(tmp_path):
    from src.security import check_allowed_directory

    # No allowlist => unrestricted (full-project investigation works)
    check_allowed_directory(str(tmp_path), ())


def test_allowed_dirs_allows_inside(tmp_path):
    from src.security import check_allowed_directory

    sub = tmp_path / "proj"
    sub.mkdir()
    check_allowed_directory(str(sub), (str(tmp_path),))


def test_allowed_dirs_blocks_outside(tmp_path):
    from src.security import SecurityError, check_allowed_directory

    with pytest.raises(SecurityError):
        check_allowed_directory("/etc", (str(tmp_path),))


def test_allowed_dirs_matches_multiple(tmp_path):
    from src.security import check_allowed_directory

    other = tmp_path / "other"
    other.mkdir()
    check_allowed_directory(str(other), (str(tmp_path / "x"), str(other)))


# --- query validation + binary detection ---


def test_validate_query_ok():
    from src.security import validate_query

    assert validate_query("hello\nworld\t", 100) == "hello\nworld\t"


def test_validate_query_too_long():
    from src.security import ValidationError, validate_query

    with pytest.raises(ValidationError):
        validate_query("x" * 11, max_length=10)


def test_validate_query_rejects_nul():
    from src.security import ValidationError, validate_query

    with pytest.raises(ValidationError):
        validate_query("a\x00b", 100)


def test_validate_query_rejects_control_char():
    from src.security import ValidationError, validate_query

    with pytest.raises(ValidationError):
        validate_query("a\x07b", 100)  # BEL


def test_validate_query_rejects_del():
    from src.security import ValidationError, validate_query

    with pytest.raises(ValidationError):
        validate_query("a\x7fb", 100)  # 0x7F DEL


def test_validate_query_rejects_c1_control():
    from src.security import ValidationError, validate_query

    with pytest.raises(ValidationError):
        validate_query("a\x85b", 100)  # 0x85 C1 NEL


def test_validate_query_allows_normal_unicode():
    from src.security import validate_query

    assert validate_query("héllo → ✓", 100) == "héllo → ✓"


def test_validate_query_rejects_non_string():
    from src.security import ValidationError, validate_query

    with pytest.raises(ValidationError):
        validate_query(123, 100)  # type: ignore[arg-type]


def test_is_text_file_binary(tmp_path):
    from src.security import is_text_file

    f = tmp_path / "b.bin"
    f.write_bytes(b"\x00\x01\x02PNG")
    assert is_text_file(str(f)) is False


def test_is_text_file_text(tmp_path):
    from src.security import is_text_file

    f = tmp_path / "t.txt"
    f.write_text("plain text")
    assert is_text_file(str(f)) is True


def test_is_text_file_missing_returns_false(tmp_path):
    from src.security import is_text_file

    assert is_text_file(str(tmp_path / "nope.txt")) is False
