"""Small, ephemeral conversation memory. No files, tools, IDs sent to the model."""

import time
from collections import OrderedDict, deque
from core.assistant_privacy import scrub_private


class ConversationMemory:
    def __init__(self, max_messages=10, ttl_seconds=1800, max_sessions=64, clock=time.monotonic):
        self.max_messages = max_messages
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self.clock = clock
        self.sessions = OrderedDict()

    def _expire(self):
        now = self.clock()
        for key, (updated, _) in list(self.sessions.items()):
            if now - updated >= self.ttl_seconds:
                del self.sessions[key]

    def read(self, key):
        self._expire()
        if key is None or key not in self.sessions:
            return []
        return [dict(message) for message in self.sessions[key][1]]

    def remember(self, key, question, answer=None, private=False):
        self._expire()
        if key is None:
            return
        _, messages = self.sessions.pop(key, (0, deque(maxlen=self.max_messages)))
        # Question-only turns: web answers carry citations (not conversation)
        # and private turns carry numbers we must not retain — the old
        # "Se consultó la web/Consulté datos privados" notes were the exact
        # bait the model later recited as a final answer.
        messages.append({"role": "user", "content": scrub_private(question)[:800]})
        if answer is not None and not private:
            messages.append({"role": "assistant", "content": scrub_private(answer)[:800]})
        self.sessions[key] = (self.clock(), messages)
        while len(self.sessions) > self.max_sessions:
            self.sessions.popitem(last=False)

    def forget(self, key):
        self.sessions.pop(key, None)
