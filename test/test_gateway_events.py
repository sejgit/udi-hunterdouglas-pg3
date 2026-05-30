"""Tests for gateway event helper utilities."""

from utils.gateway_events import (
    find_event_by_field,
    find_home_event,
    find_newest_dated_event,
    find_not_found_event,
)


class TestGatewayEventHelpers:
    def test_find_event_by_field(self):
        events = [{"evt": "home"}, {"evt": "motion-started", "id": 1}]

        assert find_event_by_field(events, "evt", "home") == events[0]
        assert find_event_by_field(events, "evt", "missing") is None

    def test_find_home_event(self):
        events = [{"evt": "scene-calc"}, {"evt": "home", "shades": [1]}]

        assert find_home_event(events)["shades"] == [1]

    def test_find_not_found_event(self):
        events = [{"message": "OK"}, {"message": "Not Found"}]

        assert find_not_found_event(events)["message"] == "Not Found"

    def test_find_newest_dated_event(self):
        events = [
            {"evt": "a", "isoDate": "2025-01-01T10:00:00.000Z"},
            {"evt": "b", "isoDate": "2025-01-01T11:00:00.000Z"},
        ]

        assert find_newest_dated_event(events)["evt"] == "a"

    def test_find_newest_dated_event_empty(self):
        assert find_newest_dated_event([{"evt": "home"}]) == {}
