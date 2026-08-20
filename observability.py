import importlib
import logging
import os


logger = logging.getLogger("gym_management")


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
