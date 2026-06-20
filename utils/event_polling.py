"""Shared helpers for node gateway event polling threads."""

from threading import Thread


def start_event_poll_thread(node, thread_name, target):
    """Start a daemon thread for gateway event polling if one is not already running."""
    if node._event_polling_thread and node._event_polling_thread.is_alive():
        return

    controller = getattr(node, "controller", node)
    controller.stop_sse_client_event.clear()
    node._event_polling_thread = Thread(target=target, name=thread_name, daemon=True)
    node._event_polling_thread.start()
