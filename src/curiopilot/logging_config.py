"""Structured logging setup for CurioPilot using structlog.

Provides human-readable console output and optional JSON file logging.
Integrates with the stdlib ``logging`` module so existing ``logging.getLogger``
calls continue to work without modification.
"""

from __future__ import annotations

import io
import logging
import sys

import structlog


def setup_logging(verbose: bool = False, json_file: str | None = None) -> None:
    """Configure structlog and stdlib logging for the process.

    Args:
        verbose: When True, set root log level to DEBUG; otherwise INFO.
        json_file: If provided, also write JSON-formatted logs to this path.
    """
    level = logging.DEBUG if verbose else logging.INFO

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    console_formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()),
        foreign_pre_chain=shared_processors,
    )

    # Bypass Rich's stderr proxy and use errors="replace" to avoid crashes
    # when log messages contain characters the Windows console can't encode.
    log_stream = io.TextIOWrapper(
        sys.__stderr__.buffer, encoding=sys.__stderr__.encoding or "utf-8", errors="replace",
    )
    console_handler = logging.StreamHandler(log_stream)
    console_handler.setFormatter(console_formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(console_handler)
    root.setLevel(level)

    if json_file:
        json_formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
        file_handler = logging.FileHandler(json_file, encoding="utf-8")
        file_handler.setFormatter(json_formatter)
        root.addHandler(file_handler)
