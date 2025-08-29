# test_gateway_events.py
from datetime import datetime, timezone, timedelta
from utils.time import get_iso_utc_now, check_timedelta_iso

# Mock class to simulate gateway event behavior
class MockGateway:
    def __init__(self):
        self.gateway_event = []
        self.gateway_events_in = False
        self.scenes_map = {}
        self.discover_called = False

    def discover(self):
        self.discover_called = True

    def gatewayEventsCheck(self):
        """
	Handles Gateway Events like homedoc-updated & scene-add (for new scenes).
	Removes unacted events only if isoDate is older than 2 minutes or invalid.
	"""

        if self.gateway_events_in:
            return

        self.gateway_events_in = True

        try:
            event_nohome = (e for e in self.gateway_event if e.get('isoDate') is not None)
            event = min(event_nohome, key=lambda x: x['isoDate'], default={})
        except (ValueError, TypeError):
            event = {}

        acted_upon = False

        if event.get('evt') == 'homedoc-updated':
            self.gateway_event.remove(event)
            acted_upon = True

        if event.get('evt') == 'scene-add':
            match = any(sc == event.get('id') for sc in self.scenes_map.keys())
            if not match:
                self.discover()
            self.gateway_event.remove(event)
            acted_upon = True

        if not acted_upon and event:
            try:
                # Compare the aware ISO date with the current aware UTC time
                if check_timedelta_iso(event.get('isoDate'), minutes = 2):
                    # LOGGER.warning(f"Unacted event!!! removed due to age > 2 min: {event}")
                    self.gateway_event.remove(event)
            except (TypeError, ValueError):
                #LOGGER.error(f"Invalid 'isoDate' in unacted event: {event}. Error: {ex}")
                self.gateway_event.remove(event)

        self.gateway_events_in = False

# ✅ Test Cases

def test_homedoc_updated_removal():
    gw = MockGateway()
    gw.gateway_event = [{"evt": "homedoc-updated", "isoDate": get_iso_utc_now()}]
    gw.gatewayEventsCheck()
    assert gw.gateway_event == []

def test_scene_add_new_triggers_discover():
    gw = MockGateway()
    gw.gateway_event = [{"evt": "scene-add", "isoDate": get_iso_utc_now(), "id": 123}]
    gw.gatewayEventsCheck()
    assert gw.discover_called is True
    assert gw.gateway_event == []

def test_scene_add_existing_does_not_trigger_discover():
    gw = MockGateway()
    gw.scenes_map = {123: "existing"}
    gw.gateway_event = [{"evt": "scene-add", "isoDate": get_iso_utc_now(), "id": 123}]
    gw.gatewayEventsCheck()
    assert gw.discover_called is False
    assert gw.gateway_event == []

def test_unacted_event_removed_if_old():
    gw = MockGateway()
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
    gw.gateway_event = [{"evt": "unknown-event", "isoDate": old_time}]
    gw.gatewayEventsCheck()
    assert gw.gateway_event == []

def test_unacted_event_kept_if_recent():
    gw = MockGateway()
    recent_time = get_iso_utc_now()
    gw.gateway_event = [{"evt": "unknown-event", "isoDate": recent_time}]
    gw.gatewayEventsCheck()
    assert gw.gateway_event != []

def test_event_removed_if_invalid_iso():
    gw = MockGateway()
    gw.gateway_event = [{"evt": "unknown-event", "isoDate": "bad-date"}]
    gw.gatewayEventsCheck()
    assert gw.gateway_event == []
