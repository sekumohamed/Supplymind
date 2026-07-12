import logging
import sys
import uuid
from contextvars import ContextVar

# Holds the current request's ID so any log call, anywhere in the call
# stack (pipeline, data_ingestion, synthesizer, cache, history), can pick
# it up without request_id being threaded through every function signature.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def new_request_id() -> str:
    return uuid.uuid4().hex[:12]


class RequestIdFilter(logging.Filter):
    """Injects the current request_id into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_ctx.get()
        return True


def setup_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | req=%(request_id)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if setup_logging() somehow gets called twice
    # (e.g. under a test runner or reload).
    root.handlers.clear()
    root.addHandler(handler)

    # Quiet down noisy third-party loggers so they don't drown out our own.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("groq").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)