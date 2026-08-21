import importlib
import json
import logging
import os
import threading
import time

from flask import g, has_request_context


logger = logging.getLogger("gym_management")
_metrics_lock = threading.Lock()
_metrics = {
    "requests_total": 0,
    "request_errors_total": 0,
    "request_duration_ms_total": 0.0,
}


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if has_request_context():
            payload["request_id"] = getattr(g, "request_id", None)
        context = getattr(record, "context", None)
        if context:
            payload["context"] = context
        return json.dumps(payload, default=str)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False


def begin_request():
    g.request_started_at = time.perf_counter()


def record_request(status_code):
    duration_ms = (time.perf_counter() - g.request_started_at) * 1000
    with _metrics_lock:
        _metrics["requests_total"] += 1
        _metrics["request_duration_ms_total"] += duration_ms
        if status_code >= 500:
            _metrics["request_errors_total"] += 1
    logger.info(
        "request completed",
        extra={"context": {
            "method": g.request_method,
            "path": g.request_path,
            "status": status_code,
            "duration_ms": round(duration_ms, 2),
        }},
    )


def metrics_snapshot():
    with _metrics_lock:
        return dict(_metrics)


def report_unexpected_error(error, context):
    logger.exception("Unexpected application error", extra={"context": context})
    if not os.environ.get("SENTRY_DSN"):
        return
    try:
        sentry_sdk = importlib.import_module("sentry_sdk")
        sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], traces_sample_rate=0.0)
        sentry_sdk.capture_exception(error)
    except ImportError:
        logger.warning("Sentry is not installed; unexpected error was only logged.")
