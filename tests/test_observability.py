import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_new_request_id_unique():
    from src.observability import new_request_id

    ids = {new_request_id() for _ in range(100)}
    assert len(ids) == 100
    assert all(len(x) >= 8 for x in ids)


def test_json_formatter_includes_fields():
    from src.observability import JsonFormatter

    rec = logging.LogRecord(
        name="antigravity_bridge",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="agy.call",
        args=(),
        exc_info=None,
    )
    rec.event = "agy.call"
    rec.request_id = "r1"
    rec.duration_ms = 12.3
    parsed = json.loads(JsonFormatter().format(rec))
    assert parsed["event"] == "agy.call"
    assert parsed["request_id"] == "r1"
    assert parsed["duration_ms"] == 12.3
    assert parsed["level"] == "INFO"


def test_setup_logging_json_handler():
    from src.observability import JsonFormatter, setup_logging

    setup_logging("INFO", "json")
    handlers = logging.getLogger().handlers
    assert any(isinstance(h.formatter, JsonFormatter) for h in handlers)


def test_setup_logging_text_handler():
    from src.observability import JsonFormatter, setup_logging

    setup_logging("INFO", "text")
    handlers = logging.getLogger().handlers
    assert all(not isinstance(h.formatter, JsonFormatter) for h in handlers)


def test_setup_logging_sets_level():
    from src.observability import setup_logging

    setup_logging("DEBUG", "text")
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_single_handler_idempotent():
    from src.observability import setup_logging

    setup_logging("INFO", "text")
    setup_logging("INFO", "text")
    assert len(logging.getLogger().handlers) == 1


def test_record_call_emits_metric(caplog):
    from src.observability import record_call

    with caplog.at_level(logging.INFO):
        record_call(request_id="r1", duration_ms=12.3, success=True, timed_out=False)
    assert any(getattr(r, "event", None) == "agy.call" for r in caplog.records)
    rec = next(r for r in caplog.records if getattr(r, "event", None) == "agy.call")
    assert rec.success is True
    assert rec.timed_out is False


def test_get_logger_returns_named_logger():
    from src.observability import LOGGER_NAME, get_logger

    assert get_logger().name == LOGGER_NAME
