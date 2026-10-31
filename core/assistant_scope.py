"""Scope is the configured channel and its public threads, never private threads."""


def public_thread(channel, parent_id):
    # Parent IDs alone are insufficient: private threads have the same parent.
    kind = getattr(getattr(channel, "type", None), "name", None)
    return (kind in {"public_thread", "news_thread"}
            and getattr(channel, "parent_id", None) == parent_id)


def channel_in_scope(channel, parent_id):
    return getattr(channel, "id", None) == parent_id or public_thread(channel, parent_id)
