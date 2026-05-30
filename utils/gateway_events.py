"""Helpers for searching and ordering gateway event queues."""

GATEWAY_EVENT_WAIT_TIMEOUT = 60.0


def find_event_by_field(events, field, value):
    """Return the first event whose field matches value."""
    for event in events:
        if event.get(field) == value:
            return event
    return None


def find_home_event(events):
    """Return the home refresh event, if present."""
    return find_event_by_field(events, "evt", "home")


def find_not_found_event(events):
    """Return an SSE error event indicating the stream endpoint was not found."""
    return find_event_by_field(events, "message", "Not Found")


def find_newest_dated_event(events):
    """Return the event with the most recent isoDate, or an empty dict."""
    dated = [event for event in events if event.get("isoDate") is not None]
    if not dated:
        return {}
    return min(dated, key=lambda event: event["isoDate"])
