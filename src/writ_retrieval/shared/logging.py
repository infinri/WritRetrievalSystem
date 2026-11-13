"""Retrieval diagnostics through standard logging, without host audit/session services.

This is diagnostic telemetry only, not Writ's durable audit log.
"""
import logging

_logger = logging.getLogger("writ_retrieval")


def emit(stream, event, session_id, mode, **fields):
    _logger.debug("%s %s", event, fields)


def emit_exception(event, exc, session_id, mode, **fields):
    _logger.warning("%s: %s (%s)", event, exc, fields)
