"""Content-free event bridge. Operational aggregates are RAM-only, restart-cleared.

Keep the historical event/execution API, but do not log arbitrary event fields,
question hashes, provider payloads, tool arguments or conversation contents.
"""
import contextvars
import logging
import re
import time
import uuid
from contextlib import contextmanager

from core.assistant_operations import operations

logger = logging.getLogger('dsbot')
current_trace = contextvars.ContextVar('boton_trace', default='standalone')
_STAGES = frozenset({'start', 'end', 'provider', 'provider_failover', 'provider_error',
                     'provider_rate_limit', 'provider_skip',
                     'http_start', 'http_end', 'http_error', 'evidence', 'ground',
                     'tool', 'tool_args', 'route', 'output', 'budget', 'model',
                     'model_finish', 'model_fallback', 'knowledge', 'search_start',
                     'search_results', 'source', 'context', 'step', 'router', 'history_scan'})


def event(stage, **fields):
    operations.record(stage, **fields)
    # Preserve content-free correlated stage logs for operators and existing
    # callers, but never format any field supplied by the caller.
    if type(stage) is str and stage in _STAGES:
        trace = current_trace.get()
        trace = trace if type(trace) is str and re.fullmatch('[0-9a-f]{12}', trace) else 'standalone'
        logger.info('Boton trace=%s stage=%s', trace, stage)


@contextmanager
def execution(question):
    token = current_trace.set(uuid.uuid4().hex[:12])
    start = time.monotonic()
    event('start')
    try:
        yield
    except BaseException:
        event('end', status='error', milliseconds=int((time.monotonic() - start) * 1000))
        raise
    else:
        event('end', status='ok', milliseconds=int((time.monotonic() - start) * 1000))
    finally:
        current_trace.reset(token)
