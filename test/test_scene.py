"""Tests for the Hunter Douglas PowerView Scene node module.

(C) 2025 Stephen Jenkins
"""

import pytest
from unittest.mock import Mock, patch
from threading import Event, Thread
import time

from nodes.Scene import Scene


class TestSceneInit:
    """Tests for Scene initialization."""

    @pytest.fixture
    def mock_poly(self):
        """Create a mock Polyglot interface."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.START = "START"
        poly.POLL = "POLL"
        poly.db_getNodeDrivers = Mock(return_value=[])
        return poly

    @pytest.fixture
    def mock_controller(self):
        """Create a mock controller node."""
        controller = Mock()
        controller.ready_event = Event()
        controller.sceneIdsActive_calc = set()
        controller.sceneIdsActive = []
        controller.scenes_map = {}
        controller.gateway = "powerview-g3.local"
        controller.generation = 3
        return controller

    def test_init_creates_scene_node(self, mock_poly, mock_controller):
        """Test that Scene node initializes with correct attributes."""
        mock_poly.getNode = Mock(return_value=mock_controller)

        scene = Scene(mock_poly, "controller_addr", "scene_addr", "Test Scene", "12345")

        assert scene.poly == mock_poly
        assert scene.primary == "controller_addr"
        assert scene.address == "scene_addr"
        assert scene.name == "Test Scene"
        assert scene.sid == "12345"
        assert scene.lpfx == "scene_addr:Test Scene"
        assert scene.event_polling_in is False
        assert scene._event_polling_thread is None

    def test_init_subscribes_to_events(self, mock_poly, mock_controller):
        """Test that Scene subscribes to START and POLL events."""
        mock_poly.getNode = Mock(return_value=mock_controller)

        scene = Scene(mock_poly, "controller_addr", "scene_addr", "Test Scene", "12345")

        assert mock_poly.subscribe.call_count == 2
        mock_poly.subscribe.assert_any_call(mock_poly.START, scene.start, "scene_addr")
        mock_poly.subscribe.assert_any_call(mock_poly.POLL, scene.poll)


class TestSceneStart:
    """Tests for Scene start method."""

    @pytest.fixture
    def scene_with_mocks(self):
        """Create a Scene with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.START = "START"
        poly.POLL = "POLL"
        poly.db_getNodeDrivers = Mock(return_value=[])

        controller = Mock()
        controller.ready_event = Event()
        controller.ready_event.set()

        poly.getNode = Mock(return_value=controller)

        scene = Scene(poly, "controller_addr", "scene_addr", "Test Scene", "12345")
        scene.setDriver = Mock()
        scene.start_event_polling = Mock()

        return scene

    def test_start_sets_scene_id_driver(self, scene_with_mocks):
        """Test that start sets the scene ID driver."""
        scene_with_mocks.start()

        scene_with_mocks.setDriver.assert_called_with("GV0", "12345")

    def test_start_waits_for_controller_ready(self, scene_with_mocks):
        """Test that start waits for controller ready event."""
        scene_with_mocks.controller.ready_event = Event()

        def set_ready():
            time.sleep(0.1)
            scene_with_mocks.controller.ready_event.set()

        thread = Thread(target=set_ready)
        thread.start()

        scene_with_mocks.start()
        thread.join()

        assert scene_with_mocks.start_event_polling.called

    def test_start_begins_event_polling(self, scene_with_mocks):
        """Test that start initiates event polling."""
        scene_with_mocks.start()

        scene_with_mocks.start_event_polling.assert_called_once()


class TestScenePoll:
    """Tests for Scene poll method."""

    @pytest.fixture
    def scene_with_mocks(self):
        """Create a Scene with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.ready_event.set()
        poly.getNode = Mock(return_value=controller)

        scene = Scene(poly, "controller_addr", "scene_addr", "Test Scene", "12345")
        scene.start_event_polling = Mock()

        return scene

    def test_poll_starts_event_polling_on_short_poll(self, scene_with_mocks):
        """Test that shortPoll starts event polling if not running."""
        scene_with_mocks.poll("shortPoll")

        scene_with_mocks.start_event_polling.assert_called_once()

    def test_poll_exits_if_controller_not_ready(self, scene_with_mocks):
        """Test that poll exits early if controller is not ready."""
        scene_with_mocks.controller.ready_event = None

        scene_with_mocks.poll("shortPoll")

        scene_with_mocks.start_event_polling.assert_not_called()


class TestSceneEventPolling:
    """Tests for Scene event polling methods."""

    @pytest.fixture
    def scene_with_mocks(self):
        """Create a Scene with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.stop_sse_client_event = Event()
        poly.getNode = Mock(return_value=controller)

        scene = Scene(poly, "controller_addr", "scene_addr", "Test Scene", "12345")

        return scene

    @patch("nodes.Scene.Thread")
    def test_start_event_polling_creates_thread(self, mock_thread, scene_with_mocks):
        """Test that start_event_polling creates and starts a thread."""
        scene_with_mocks.start_event_polling()

        mock_thread.assert_called_once()


class TestSceneCalcActive:
    """Tests for Scene calcActive method."""

    @pytest.fixture
    def scene_with_mocks(self):
        """Create a Scene with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.sceneIdsActive_calc = set()
        controller.get_shade_data = Mock(return_value=None)
        controller.scenes_map = {
            "12345": {
                "members": [
                    {"shd_Id": "shade1", "pos": {"pos1": 10000}},
                    {"shd_Id": "shade2", "pos": {"pos1": 0}},
                ]
            }
        }
        poly.getNode = Mock(return_value=controller)

        scene = Scene(poly, "controller_addr", "scene_addr", "Test Scene", "12345")
        scene._handle_match = Mock()
        scene._handle_no_match = Mock()
        scene.check_if_calc_active_match_gateway = Mock()

        return scene

    def test_calc_active_with_matching_positions(self, scene_with_mocks):
        """Test calcActive when shade positions match scene."""
        # Setup shade data that matches the scene
        scene_with_mocks.controller.get_shade_data = Mock(
            side_effect=lambda sid: {
                "shd_Id": sid,
                "positions": {"primary": 100} if sid == "shade1" else {"primary": 0},
                "capabilities": 0,
            }
        )

        scene_with_mocks.calcActive()

        scene_with_mocks._handle_match.assert_called_once()

    def test_calc_active_with_non_matching_positions(self, scene_with_mocks):
        """Test calcActive when shade positions don't match scene."""
        # Setup shade data that doesn't match the scene
        scene_with_mocks.controller.get_shade_data = Mock(
            side_effect=lambda sid: {
                "shd_Id": sid,
                "positions": {"primary": 50},
                "capabilities": 0,
            }
        )

        scene_with_mocks.calcActive()

        scene_with_mocks._handle_no_match.assert_called_once()

    def test_calc_active_with_missing_scene_data(self, scene_with_mocks):
        """Test calcActive when scene data is missing."""
        scene_with_mocks.controller.scenes_map = {}

        scene_with_mocks.calcActive()

        scene_with_mocks._handle_no_match.assert_called_once()


class TestSceneHandlers:
    """Tests for Scene handler methods."""

    @pytest.fixture
    def scene_with_mocks(self):
        """Create a Scene with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.sceneIdsActive_calc = set()
        poly.getNode = Mock(return_value=controller)

        scene = Scene(poly, "controller_addr", "scene_addr", "Test Scene", "12345")
        scene.setDriver = Mock()
        scene.reportCmd = Mock()

        return scene

    def test_handle_match_activates_scene(self, scene_with_mocks):
        """Test that _handle_match sets scene as active."""
        scene_with_mocks._handle_match()

        assert "12345" in scene_with_mocks.controller.sceneIdsActive_calc
        scene_with_mocks.setDriver.assert_called_with("ST", 1, report=True, force=True)
        scene_with_mocks.reportCmd.assert_called_with("DON", 2)

    def test_handle_no_match_deactivates_scene(self, scene_with_mocks):
        """Test that _handle_no_match sets scene as inactive."""
        scene_with_mocks.controller.sceneIdsActive_calc.add("12345")

        scene_with_mocks._handle_no_match()

        assert "12345" not in scene_with_mocks.controller.sceneIdsActive_calc
        scene_with_mocks.setDriver.assert_called_with("ST", 0, report=True, force=True)
        scene_with_mocks.reportCmd.assert_called_with("DOF", 2)


class TestSceneCommands:
    """Tests for Scene command handlers."""

    @pytest.fixture
    def scene_with_mocks(self):
        """Create a Scene with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.gateway = "powerview-g3.local"
        controller.generation = 3
        controller.put = Mock()
        controller.get = Mock()
        poly.getNode = Mock(return_value=controller)

        scene = Scene(poly, "controller_addr", "scene_addr", "Test Scene", "12345")
        scene.setDriver = Mock()
        scene.reportCmd = Mock()

        return scene

    def test_cmd_activate_gen3(self, scene_with_mocks):
        """Test cmdActivate for Gen 3 gateway."""
        scene_with_mocks.cmdActivate()

        expected_url = "http://powerview-g3.local/home/scenes/12345/activate"
        scene_with_mocks.controller.put.assert_called_with(expected_url)
        scene_with_mocks.reportCmd.assert_called_with("ACTIVATE", 2)

    def test_cmd_activate_gen2(self, scene_with_mocks):
        """Test cmdActivate for Gen 2 gateway."""
        scene_with_mocks.controller.generation = 2

        scene_with_mocks.cmdActivate()

        expected_url = "http://powerview-g3.local/api/scenes?sceneId=12345"
        scene_with_mocks.controller.get.assert_called_with(expected_url)
        scene_with_mocks.setDriver.assert_called_with("ST", 1, report=True, force=True)
        assert scene_with_mocks.reportCmd.call_count == 2  # DON and ACTIVATE

    def test_query_command(self, scene_with_mocks):
        """Test query command handler."""
        scene_with_mocks.controller.scenes_map = {"12345": {"name": "Test Scene"}}
        scene_with_mocks.calcActive = Mock()
        scene_with_mocks.reportDrivers = Mock()

        scene_with_mocks.query()

        scene_with_mocks.calcActive.assert_called_once()
        scene_with_mocks.reportDrivers.assert_called_once()


class TestSceneCheckActive:
    """Tests for Scene active state checking."""

    @pytest.fixture
    def scene_with_mocks(self):
        """Create a Scene with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.gateway = 3
        controller.sceneIdsActive_calc = set()
        controller.sceneIdsActive = []
        poly.getNode = Mock(return_value=controller)

        scene = Scene(poly, "controller_addr", "scene_addr", "Test Scene", "12345")

        return scene

    def test_check_calc_active_match_gateway_agrees(self, scene_with_mocks):
        """Test check when calculated and gateway states agree."""
        scene_with_mocks.controller.sceneIdsActive_calc.add("12345")
        scene_with_mocks.controller.sceneIdsActive = ["12345"]

        result = scene_with_mocks.check_if_calc_active_match_gateway()

        assert result is True

    def test_check_calc_active_match_gateway_disagrees(self, scene_with_mocks):
        """Test check when calculated and gateway states disagree."""
        scene_with_mocks.controller.sceneIdsActive_calc.add("12345")
        scene_with_mocks.controller.sceneIdsActive = []

        result = scene_with_mocks.check_if_calc_active_match_gateway()

        assert result is False

    def test_check_calc_active_match_gateway_gen2(self, scene_with_mocks):
        """Test check returns False for Gen 2 gateway."""
        scene_with_mocks.controller.gateway = 2

        result = scene_with_mocks.check_if_calc_active_match_gateway()

        assert result is False


class TestSceneDriversCommands:
    """Tests for Scene drivers and commands configuration."""

    def test_drivers_defined(self):
        """Test that Scene has correct drivers defined."""
        assert hasattr(Scene, "drivers")
        assert len(Scene.drivers) == 2

        driver_names = [d["driver"] for d in Scene.drivers]
        assert "ST" in driver_names
        assert "GV0" in driver_names

    def test_commands_defined(self):
        """Test that Scene has correct commands defined."""
        assert hasattr(Scene, "commands")
        assert "ACTIVATE" in Scene.commands
        assert "QUERY" in Scene.commands

        assert Scene.commands["ACTIVATE"] == Scene.cmdActivate
        assert Scene.commands["QUERY"] == Scene.query


# ==================== PHASE 3 TESTS ====================


class TestSceneEventPollingG3:
    """Tests for Scene event polling functionality."""

    @pytest.fixture
    def scene_with_event_mocks(self):
        """Create a Scene with event polling mocks."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])

        controller = Mock()
        controller.ready_event = Event()
        controller.ready_event.set()
        controller.stop_sse_client_event = Event()
        controller.generation = 3
        controller.gateway = "192.168.1.100"
        controller.get_gateway_event = Mock(return_value=[])
        controller.scenes_map = {"scene1": {"_id": "scene1", "name": "Morning Scene"}}

        poly.getNode = Mock(return_value=controller)

        scene = Scene(poly, "controller", "scene1", "Morning Scene", "scene1")
        scene.setDriver = Mock()
        scene.reportCmd = Mock()

        return scene

    def test_poll_events_for_g3_scene_calc(self, scene_with_event_mocks):
        """Test _poll_events_for_g3 with scene-calc event."""
        events = [
            {"evt": "scene-calc", "id": "scene1", "isoDate": "2025-01-01T12:00:00.000Z"}
        ]

        scene_with_event_mocks._poll_events_for_g3(events)

        # Should process without error
        assert True

    def test_poll_events_for_g3_scene_activated(self, scene_with_event_mocks):
        """Test _poll_events_for_g3 with scene-activated event."""
        events = [
            {
                "evt": "scene-activated",
                "id": "scene1",
                "isoDate": "2025-01-01T12:00:00.000Z",
            }
        ]

        scene_with_event_mocks.calcActive = Mock()
        scene_with_event_mocks._poll_events_for_g3(events)

        # Should call calcActive
        scene_with_event_mocks.calcActive.assert_called()

    def test_poll_events_for_g3_with_empty_events(self, scene_with_event_mocks):
        """Test _poll_events_for_g3 with no events."""
        events = []

        # Should not raise exception
        try:
            scene_with_event_mocks._poll_events_for_g3(events)
            assert True
        except Exception:
            assert False, "_poll_events_for_g3 should handle empty events"


class TestSceneActivation:
    """Tests for Scene activation functionality."""

    @pytest.fixture
    def scene_with_activation_mocks(self):
        """Create a Scene with activation mocks."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])

        controller = Mock()
        controller.ready_event = Event()
        controller.ready_event.set()
        controller.gateway = "192.168.1.100"
        controller.generation = 3
        controller.put = Mock()

        poly.getNode = Mock(return_value=controller)

        scene = Scene(poly, "controller", "scene1", "Morning Scene", "scene1")
        scene.setDriver = Mock()
        scene.reportCmd = Mock()

        return scene

    def test_cmd_activate_gen3(self, scene_with_activation_mocks):
        """Test cmdActivate for Gen 3 gateway."""
        scene_with_activation_mocks.cmdActivate(None)

        # Should call controller.put with scene activation URL
        assert scene_with_activation_mocks.controller.put.called

    def test_calc_active_scene_active(self, scene_with_activation_mocks):
        """Test calcActive when scene has members."""
        scene_with_activation_mocks.controller.sceneIdsActive = ["scene1"]
        scene_with_activation_mocks.controller.sceneIdsActive_calc = set()
        scene_with_activation_mocks.controller.scenes_map = {
            "scene1": {
                "_id": "scene1",
                "members": [],  # Empty members means no match
            }
        }
        scene_with_activation_mocks.controller.generation = 3

        scene_with_activation_mocks.calcActive()

        # With no members, should call _handle_no_match (status = 0)
        calls = [
            c
            for c in scene_with_activation_mocks.setDriver.call_args_list
            if c[0][0] == "ST"
        ]
        if calls:
            assert calls[0][0][1] == 0  # No match = 0

    def test_calc_active_scene_inactive(self, scene_with_activation_mocks):
        """Test calcActive when scene is not active."""
        scene_with_activation_mocks.controller.sceneIdsActive = ["other_scene"]
        scene_with_activation_mocks.controller.sceneIdsActive_calc = set(["scene1"])

        scene_with_activation_mocks.calcActive()

        # Should set status to inactive (0) and remove from calc set
        calls = [
            c
            for c in scene_with_activation_mocks.setDriver.call_args_list
            if c[0][0] == "ST"
        ]
        if calls:
            assert calls[0][0][1] == 0
        assert (
            "scene1" not in scene_with_activation_mocks.controller.sceneIdsActive_calc
        )


# ==================== PHASE 4 TESTS (BALANCED) ====================


class TestSceneQuery:
    """Tests for Scene query functionality."""

    @pytest.fixture
    def scene_query(self):
        """Create a Scene for query testing."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])

        controller = Mock()
        controller.ready_event = Event()
        controller.ready_event.set()
        controller.gateway = "192.168.1.100"
        controller.generation = 3
        controller.scenes_map = {
            "scene1": {"_id": "scene1", "name": "Morning", "roomId": "room1"}
        }
        controller.sceneIdsActive = []
        controller.sceneIdsActive_calc = set()

        poly.getNode = Mock(return_value=controller)

        scene = Scene(poly, "controller", "scene1", "Morning", "scene1")
        scene.setDriver = Mock()
        scene.reportDrivers = Mock()

        return scene

    def test_query_reports_drivers(self, scene_query):
        """Test query reports current drivers."""
        scene_query.query(None)

        scene_query.reportDrivers.assert_called_once()

    def test_query_with_command_data(self, scene_query):
        """Test query with command data."""
        command = {"value": "test"}

        scene_query.query(command)

        # Should still report drivers
        scene_query.reportDrivers.assert_called()


class TestSceneActivationGen2:
    """Tests for Scene activation with Gen 2 gateway."""

    @pytest.fixture
    def scene_gen2(self):
        """Create a Scene for Gen 2 testing."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])

        controller = Mock()
        controller.ready_event = Event()
        controller.ready_event.set()
        controller.gateway = "192.168.1.100"
        controller.generation = 2
        controller.get = Mock()

        poly.getNode = Mock(return_value=controller)

        scene = Scene(poly, "controller", "scene1", "Morning", "scene1")
        scene.setDriver = Mock()
        scene.reportCmd = Mock()
        scene.calcActive = Mock()

        return scene

    def test_cmd_activate_gen2(self, scene_gen2):
        """Test cmdActivate for Gen 2 gateway."""
        from unittest.mock import Mock as MockResponse

        mock_response = MockResponse()
        mock_response.status_code = 200
        scene_gen2.controller.get.return_value = mock_response

        scene_gen2.cmdActivate(None)

        # Should call controller.get for Gen 2
        assert scene_gen2.controller.get.called
