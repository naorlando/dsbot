"""Shared best-effort credential scrubbing; never a complete PII detector."""
import re

SECRET_PATTERN = re.compile(
    r"(?:sk-or-v1-|tvly-(?:dev|prod)-|mfa\.|gsk_)[A-Za-z0-9_-]{12,}"
    r"|AIza[A-Za-z0-9_-]{30,}"
    r"|[A-Za-z0-9_-]{23,28}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}"
)
