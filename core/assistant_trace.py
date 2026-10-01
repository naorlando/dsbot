"""Correlated stage logs, deliberately excluding conversations and tool contents."""
import contextvars
import hashlib
import logging
import time
import uuid
from contextlib import contextmanager

logger = logging.getLogger('dsbot')
current_trace = contextvars.ContextVar('boton_trace', default='standalone')


def event(stage, **fields):
    logger.info('Boton trace=%s stage=%s %s', current_trace.get(), stage,
                ' '.join(f'{key}={value}' for key, value in fields.items()))


@contextmanager
def execution(question):
    token = current_trace.set(uuid.uuid4().hex[:12])
    start = time.monotonic()
    event('start', question_chars=len(question) if isinstance(question, str) else 0,
          question_hash=hashlib.sha256(str(question).encode()).hexdigest()[:12])
    try:
        yield
    except BaseException as exc:
        event('end', status='error', error=type(exc).__name__, milliseconds=int((time.monotonic() - start) * 1000))
        raise
    else:
        event('end', status='ok', milliseconds=int((time.monotonic() - start) * 1000))
    finally:
        current_trace.reset(token)
