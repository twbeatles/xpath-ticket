import logging

from xpath_explorer.runtime import (
    ErrorTelemetryHandler,
    ErrorTelemetryStore,
    setup_logger,
)


def test_error_telemetry_store_records_summary_and_recent_events():
    store = ErrorTelemetryStore(max_events=3)

    err1 = logging.LogRecord(
        name="XPathExplorer",
        level=logging.ERROR,
        pathname=__file__,
        lineno=10,
        msg="first failure %s",
        args=("A",),
        exc_info=None,
    )
    err2 = logging.LogRecord(
        name="XPathExplorer",
        level=logging.ERROR,
        pathname=__file__,
        lineno=20,
        msg="second failure",
        args=(),
        exc_info=None,
    )
    crit = logging.LogRecord(
        name="XPathExplorer",
        level=logging.CRITICAL,
        pathname=__file__,
        lineno=30,
        msg="critical failure",
        args=(),
        exc_info=None,
    )

    store.record(err1)
    store.record(err1)
    store.record(err2)
    store.record(crit)

    summary = store.get_summary(top_n=5)
    assert summary["total_errors"] == 4
    assert summary["critical_count"] == 1
    assert summary["buffered_events"] == 3
    assert summary["unique_error_types"] == 3
    assert summary["top_errors"][0]["count"] == 2

    recent = store.get_recent_events(limit=2)
    assert len(recent) == 2
    assert recent[0].message == "critical failure"

    report = store.render_markdown_report(top_n=5, recent_limit=2)
    assert "Error Telemetry Report" in report
    assert "Top Error Types" in report
    assert "Recent Error Events" in report


def test_error_telemetry_handler_captures_error_only():
    store = ErrorTelemetryStore(max_events=10)
    handler = ErrorTelemetryHandler(store)

    logger = logging.getLogger("test.error.telemetry.handler")
    logger.handlers = []
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    logger.addHandler(handler)

    logger.warning("warning message")
    logger.error("error message")

    summary = store.get_summary(top_n=5)
    assert summary["total_errors"] == 1
    assert summary["critical_count"] == 0


def test_setup_logger_registers_single_telemetry_handler():
    logger = setup_logger()
    handlers = [h for h in logger.handlers if isinstance(h, ErrorTelemetryHandler)]
    assert len(handlers) == 1
