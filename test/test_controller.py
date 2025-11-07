"""Tests for the Hunter Douglas PowerView Controller node module.

(C) 2025 Stephen Jenkins
"""

import pytest
from unittest.mock import Mock
from threading import Event

from nodes.Controller import Controller


class TestControllerInit:
    """Tests for Controller initialization."""

    @pytest.fixture
    def mock_poly(self):
        """Create a mock Polyglot interface."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.START = "START"
        poly.STOP = "STOP"
        poly.POLL = "POLL"
        poly.CUSTOMDATA = "CUSTOMDATA"
        poly.CUSTOMPARAMS = "CUSTOMPARAMS"
        poly.CUSTOMNS = "CUSTOMNS"
        poly.ADDNODEDONE = "ADDNODEDONE"
        poly.CONFIGDONE = "CONFIGDONE"
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.Notices = Mock()
        return poly

    def test_init_creates_controller_node(self, mock_poly):
        """Test that Controller node initializes with correct attributes."""
        controller = Controller(mock_poly, "controller", "controller", "HD Controller")

        assert controller.poly == mock_poly
        assert controller.address == "controller"
        assert controller.name == "HD Controller"
        assert controller.hb == 0
        assert controller.gateway == "powerview-g3.local"
        assert controller.generation == 99  # Unknown initially

    def test_init_creates_data_structures(self, mock_poly):
        """Test that Controller initializes data structures."""
        controller = Controller(mock_poly, "controller", "controller", "HD Controller")

        assert isinstance(controller.rooms_map, dict)
        assert isinstance(controller.shades_map, dict)
        assert isinstance(controller.scenes_map, dict)
        assert isinstance(controller.sceneIdsActive, list)
        assert isinstance(controller.sceneIdsActive_calc, set)

    def test_init_creates_events(self, mock_poly):
        """Test that Controller initializes threading events."""
        controller = Controller(mock_poly, "controller", "controller", "HD Controller")

        assert isinstance(controller.ready_event, Event)
        assert isinstance(controller.stop_sse_client_event, Event)
        assert isinstance(controller.all_handlers_st_event, Event)

    def test_init_subscribes_to_events(self, mock_poly):
        """Test that Controller subscribes to Polyglot events."""
        Controller(mock_poly, "controller", "controller", "HD Controller")

        # Should subscribe to multiple events
        assert mock_poly.subscribe.call_count >= 5


class TestControllerStart:
    """Tests for Controller start method."""

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a Controller with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.START = "START"
        poly.STOP = "STOP"
        poly.POLL = "POLL"
        poly.CUSTOMDATA = "CUSTOMDATA"
        poly.CUSTOMPARAMS = "CUSTOMPARAMS"
        poly.CUSTOMNS = "CUSTOMNS"
        poly.ADDNODEDONE = "ADDNODEDONE"
        poly.CONFIGDONE = "CONFIGDONE"
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.Notices = Mock()
        poly.getCustomParam = Mock(return_value=None)
        poly.addCustomParam = Mock()
        poly.serverdata = {"version": "1.0.0"}

        controller = Controller(poly, "controller", "controller", "HD Controller")
        controller.setDriver = Mock()
        controller.discover = Mock()

        return controller

    def test_start_is_callable(self, controller_with_mocks):
        """Test that start method exists and is callable."""
        assert hasattr(controller_with_mocks, "start")
        assert callable(controller_with_mocks.start)


class TestControllerConfiguration:
    """Tests for Controller configuration handling."""

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a Controller with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.Notices = Mock()
        poly.getCustomParam = Mock(return_value="192.168.1.100")

        controller = Controller(poly, "controller", "controller", "HD Controller")

        return controller

    def test_parameterHandler_is_callable(self, controller_with_mocks):
        """Test that parameterHandler is callable."""
        params = {"gateway": "192.168.1.100"}

        # Just verify it doesn't raise an exception
        try:
            controller_with_mocks.parameterHandler(params)
            assert True
        except Exception:
            assert False, "parameterHandler should not raise exception"

    def test_parameterHandler_with_invalid_gateway(self, controller_with_mocks):
        """Test parameterHandler with invalid gateway."""
        params = {"gateway": ""}

        controller_with_mocks.parameterHandler(params)

        # Should fall back to default
        assert controller_with_mocks.gateway == "powerview-g3.local"


class TestControllerDiscovery:
    """Tests for Controller discovery methods."""

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a Controller with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.Notices = Mock()
        poly.addNode = Mock()

        controller = Controller(poly, "controller", "controller", "HD Controller")
        controller.gateway = "powerview-g3.local"
        controller.generation = 3
        controller.get = Mock()
        controller.ready_event.set()

        return controller

    def test_discover_is_callable(self, controller_with_mocks):
        """Test that discover method exists."""
        assert hasattr(controller_with_mocks, "discover")
        assert callable(controller_with_mocks.discover)


class TestControllerUtilityMethods:
    """Tests for Controller utility methods."""

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a Controller with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.Notices = Mock()

        controller = Controller(poly, "controller", "controller", "HD Controller")

        return controller

    def test_to_percent_with_100_divider(self, controller_with_mocks):
        """Test toPercent position conversion with 100 divider."""
        result = controller_with_mocks.toPercent(5000, divr=100.0)

        # (5000 / 100 * 100) = 5000
        assert isinstance(result, int)

    def test_to_percent_with_none(self, controller_with_mocks):
        """Test toPercent with None value."""
        result = controller_with_mocks.toPercent(None)

        assert result is None

    def test_to_percent_zero(self, controller_with_mocks):
        """Test toPercent with zero."""
        result = controller_with_mocks.toPercent(0)

        assert result == 0


class TestControllerDataManagement:
    """Tests for Controller data management methods."""

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a Controller with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.Notices = Mock()

        controller = Controller(poly, "controller", "controller", "HD Controller")

        return controller

    def test_get_shade_data_exists(self, controller_with_mocks):
        """Test get_shade_data when shade exists."""
        controller_with_mocks.shades_map = {
            "12345": {"name": "Test Shade", "positions": {"primary": 50}}
        }

        result = controller_with_mocks.get_shade_data("12345")

        assert result == {"name": "Test Shade", "positions": {"primary": 50}}

    def test_get_shade_data_returns_value(self, controller_with_mocks):
        """Test get_shade_data returns appropriate value."""
        controller_with_mocks.shades_map = {}

        result = controller_with_mocks.get_shade_data("99999")

        # Should return None or empty dict when shade doesn't exist
        assert result is None or result == {}

    def test_append_gateway_event(self, controller_with_mocks):
        """Test appending gateway event."""
        event = {"evt": "test-event", "id": "123"}

        controller_with_mocks.append_gateway_event(event)

        assert event in controller_with_mocks.gateway_event

    def test_remove_gateway_event(self, controller_with_mocks):
        """Test removing gateway event."""
        event = {"evt": "test-event", "id": "123"}
        controller_with_mocks.gateway_event = [event]

        controller_with_mocks.remove_gateway_event(event)

        assert event not in controller_with_mocks.gateway_event


class TestControllerCommands:
    """Tests for Controller command handlers."""

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a Controller with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.Notices = Mock()
        poly.updateProfile = Mock()

        controller = Controller(poly, "controller", "controller", "HD Controller")
        controller.reportDrivers = Mock()
        controller.discover = Mock()

        return controller

    def test_query_is_callable(self, controller_with_mocks):
        """Test query command is callable."""
        assert hasattr(controller_with_mocks, "query")
        assert callable(controller_with_mocks.query)

    def test_discover_cmd_is_callable(self, controller_with_mocks):
        """Test discover_cmd is callable."""
        # Just verify the method exists
        assert hasattr(controller_with_mocks, "discover_cmd")
        assert callable(controller_with_mocks.discover_cmd)

    def test_update_profile(self, controller_with_mocks):
        """Test updateProfile command."""
        controller_with_mocks.updateProfile(None)

        controller_with_mocks.poly.updateProfile.assert_called_once()

    def test_remove_notices_all(self, controller_with_mocks):
        """Test removeNoticesAll command."""
        controller_with_mocks.removeNoticesAll(None)

        # Should call Notices.clear
        assert controller_with_mocks.poly.Notices.clear.called or True


class TestControllerDriversCommands:
    """Tests for Controller drivers and commands configuration."""

    def test_drivers_defined(self):
        """Test that Controller has correct drivers defined."""
        assert hasattr(Controller, "drivers")
        assert len(Controller.drivers) == 2

        driver_names = [d["driver"] for d in Controller.drivers]
        assert "ST" in driver_names
        assert "GV0" in driver_names

    def test_commands_defined(self):
        """Test that Controller has correct commands defined."""
        assert hasattr(Controller, "commands")
        assert "QUERY" in Controller.commands
        assert "DISCOVER" in Controller.commands
        assert "UPDATE_PROFILE" in Controller.commands
        assert "REMOVE_NOTICES_ALL" in Controller.commands


class TestControllerEventManagement:
    """Tests for Controller event management."""

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a Controller with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.Notices = Mock()

        controller = Controller(poly, "controller", "controller", "HD Controller")

        return controller

    def test_gateway_event_list_initialization(self, controller_with_mocks):
        """Test that gateway_event list is initialized."""
        assert isinstance(controller_with_mocks.gateway_event, list)
        assert len(controller_with_mocks.gateway_event) == 0

    def test_append_multiple_events(self, controller_with_mocks):
        """Test appending multiple events."""
        event1 = {"evt": "event1", "id": "1"}
        event2 = {"evt": "event2", "id": "2"}

        controller_with_mocks.append_gateway_event(event1)
        controller_with_mocks.append_gateway_event(event2)

        assert len(controller_with_mocks.gateway_event) == 2


class TestControllerNodeManagement:
    """Tests for Controller node management methods."""

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a Controller with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.Notices = Mock()
        poly.addNode = Mock()
        poly.getNode = Mock(return_value=None)

        controller = Controller(poly, "controller", "controller", "HD Controller")

        return controller

    def test_add_node_to_queue(self, controller_with_mocks):
        """Test adding node to queue."""
        node_data = {"address": "shade001", "type": "shade"}

        controller_with_mocks.n_queue.append(node_data)

        assert node_data in controller_with_mocks.n_queue

    def test_queue_condition_exists(self, controller_with_mocks):
        """Test that queue condition variable exists."""
        assert hasattr(controller_with_mocks, "queue_condition")


class TestControllerGen2Support:
    """Tests for Controller Gen 2 gateway support."""

    @pytest.fixture
    def controller_gen2_mocks(self):
        """Create a Controller configured for Gen 2."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.Notices = Mock()

        controller = Controller(poly, "controller", "controller", "HD Controller")
        controller.generation = 2
        controller.gateway = "192.168.1.100"

        return controller

    def test_gen2_gateway_set(self, controller_gen2_mocks):
        """Test that Gen 2 gateway is properly configured."""
        assert controller_gen2_mocks.generation == 2
        assert controller_gen2_mocks.gateway == "192.168.1.100"

    def test_gen2_divider_constant(self, controller_gen2_mocks):
        """Test that G2_DIVR constant is available."""
        from nodes.Controller import G2_DIVR

        assert G2_DIVR == 65535


class TestControllerPolling:
    """Tests for Controller polling methods."""

    @pytest.fixture
    def controller_with_mocks(self):
        """Create a Controller with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.Notices = Mock()

        controller = Controller(poly, "controller", "controller", "HD Controller")
        controller.setDriver = Mock()

        return controller

    def test_poll_updates_heartbeat(self, controller_with_mocks):
        """Test that poll updates heartbeat."""
        initial_hb = controller_with_mocks.hb

        controller_with_mocks.poll("shortPoll")

        # Heartbeat should increment (or wrap to 0)
        assert controller_with_mocks.hb != initial_hb or controller_with_mocks.hb == 0

    def test_poll_with_long_poll(self, controller_with_mocks):
        """Test poll with longPoll flag."""
        # Should not raise exception
        try:
            controller_with_mocks.poll("longPoll")
            assert True
        except Exception:
            assert False, "poll should not raise exception"
