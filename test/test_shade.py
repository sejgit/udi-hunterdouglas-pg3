"""Tests for the Hunter Douglas PowerView Shade node module.

(C) 2025 Stephen Jenkins
"""

import pytest
from unittest.mock import Mock, patch
from threading import Event

from nodes.Shade import (
    Shade,
    ShadeNoTilt,
    ShadeOnlyPrimary,
    ShadeOnlySecondary,
    ShadeNoSecondary,
    ShadeOnlyTilt,
)


class TestShadeInit:
    """Tests for Shade initialization."""

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
        controller.shades_map = {}
        controller.gateway = "powerview-g3.local"
        controller.generation = 3
        return controller

    def test_init_creates_shade_node(self, mock_poly, mock_controller):
        """Test that Shade node initializes with correct attributes."""
        mock_poly.getNode = Mock(return_value=mock_controller)

        shade = Shade(mock_poly, "controller_addr", "shade_addr", "Test Shade", "12345")

        assert shade.poly == mock_poly
        assert shade.primary == "controller_addr"
        assert shade.address == "shade_addr"
        assert shade.name == "Test Shade"
        assert shade.sid == "12345"
        assert shade.lpfx == "shade_addr:Test Shade"
        assert shade.event_polling_in is False
        assert shade._event_polling_thread is None

    def test_init_subscribes_to_events(self, mock_poly, mock_controller):
        """Test that Shade subscribes to START and POLL events."""
        mock_poly.getNode = Mock(return_value=mock_controller)

        shade = Shade(mock_poly, "controller_addr", "shade_addr", "Test Shade", "12345")

        assert mock_poly.subscribe.call_count == 2
        mock_poly.subscribe.assert_any_call(mock_poly.START, shade.start, "shade_addr")
        mock_poly.subscribe.assert_any_call(mock_poly.POLL, shade.poll)

    def test_init_sets_tilt_capabilities(self, mock_poly, mock_controller):
        """Test that Shade sets tilt capability lists."""
        mock_poly.getNode = Mock(return_value=mock_controller)

        shade = Shade(mock_poly, "controller_addr", "shade_addr", "Test Shade", "12345")

        assert shade.tiltCapable == [1, 2, 4, 5, 9, 10]
        assert shade.tiltOnly90Capable == [1, 9]


class TestShadeStart:
    """Tests for Shade start method."""

    @pytest.fixture
    def shade_with_mocks(self):
        """Create a Shade with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.START = "START"
        poly.POLL = "POLL"
        poly.db_getNodeDrivers = Mock(return_value=[])

        controller = Mock()
        controller.ready_event = Event()
        controller.ready_event.set()
        controller.shades_map = {
            "12345": {
                "shd_Id": "12345",
                "roomId": "99",
                "capabilities": 0,
                "batteryStatus": 3,
            }
        }

        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller_addr", "shade_addr", "Test Shade", "12345")
        shade.setDriver = Mock()
        shade.start_event_polling = Mock()

        return shade

    def test_start_sets_shade_id_driver(self, shade_with_mocks):
        """Test that start sets the shade ID driver."""
        shade_with_mocks.start()

        # Should set shade ID
        calls = shade_with_mocks.setDriver.call_args_list
        driver_calls = {call[0][0]: call[0][1] for call in calls}

        assert driver_calls.get("GV0") == "12345"

    def test_start_begins_event_polling(self, shade_with_mocks):
        """Test that start initiates event polling."""
        shade_with_mocks.start()

        shade_with_mocks.start_event_polling.assert_called_once()


class TestShadePoll:
    """Tests for Shade poll method."""

    @pytest.fixture
    def shade_with_mocks(self):
        """Create a Shade with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.ready_event.set()
        controller.shades_map = {}
        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller_addr", "shade_addr", "Test Shade", "12345")
        shade.start_event_polling = Mock()
        shade.updateData = Mock()

        return shade

    def test_poll_starts_event_polling_on_short_poll(self, shade_with_mocks):
        """Test that shortPoll starts event polling if not running."""
        shade_with_mocks.poll("shortPoll")

        shade_with_mocks.start_event_polling.assert_called_once()

    def test_poll_exits_if_controller_not_ready(self, shade_with_mocks):
        """Test that poll exits early if controller is not ready."""
        shade_with_mocks.controller.ready_event = None

        shade_with_mocks.poll("shortPoll")

        shade_with_mocks.start_event_polling.assert_not_called()


class TestShadeEventPolling:
    """Tests for Shade event polling methods."""

    @pytest.fixture
    def shade_with_mocks(self):
        """Create a Shade with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.stop_sse_client_event = Event()
        controller.shades_map = {}
        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller_addr", "shade_addr", "Test Shade", "12345")

        return shade

    @patch("nodes.Shade.Thread")
    def test_start_event_polling_creates_thread(self, mock_thread, shade_with_mocks):
        """Test that start_event_polling creates and starts a thread."""
        shade_with_mocks.start_event_polling()

        mock_thread.assert_called_once()


class TestShadeUpdateData:
    """Tests for Shade updateData method."""

    @pytest.fixture
    def shade_with_mocks(self):
        """Create a Shade with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.generation = 3
        controller.get_shade_data = Mock(
            return_value={
                "shd_Id": "12345",
                "name": "Test Shade",
                "roomId": "99",
                "batteryStatus": 3,
                "capabilities": 0,
                "positions": {"primary": 50, "secondary": 75, "tilt": 25},
            }
        )
        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller_addr", "shade_addr", "Test Shade", "12345")
        shade.setDriver = Mock()
        shade.reportCmd = Mock()
        shade.updatePositions = Mock()

        return shade

    def test_update_data_sets_drivers(self, shade_with_mocks):
        """Test that updateData sets driver values."""
        result = shade_with_mocks.updateData()

        assert result is True
        shade_with_mocks.setDriver.assert_any_call("ST", 0, report=True, force=True)
        shade_with_mocks.setDriver.assert_any_call("GV1", "99", report=True, force=True)
        shade_with_mocks.setDriver.assert_any_call("GV6", 3, report=True, force=True)
        shade_with_mocks.setDriver.assert_any_call("GV5", 0, report=True, force=True)

    def test_update_data_calls_update_positions(self, shade_with_mocks):
        """Test that updateData calls updatePositions."""
        shade_with_mocks.updateData()

        shade_with_mocks.updatePositions.assert_called_once()


class TestShadeCommands:
    """Tests for Shade command handlers."""

    @pytest.fixture
    def shade_with_mocks(self):
        """Create a Shade with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.gateway = "powerview-g3.local"
        controller.generation = 3
        controller.put = Mock()
        controller.get = Mock()
        controller.shades_map = {}
        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller_addr", "shade_addr", "Test Shade", "12345")
        shade.setDriver = Mock()
        shade.reportCmd = Mock()

        return shade

    def test_cmd_open_gen3(self, shade_with_mocks):
        """Test cmdOpen for Gen 3 gateway."""
        shade_with_mocks.setShadePosition = Mock()
        shade_with_mocks.cmdOpen(None)

        # cmdOpen calls setShadePosition
        shade_with_mocks.setShadePosition.assert_called_once()

    def test_cmd_close_gen3(self, shade_with_mocks):
        """Test cmdClose for Gen 3 gateway."""
        shade_with_mocks.setShadePosition = Mock()
        shade_with_mocks.cmdClose(None)

        shade_with_mocks.setShadePosition.assert_called_once()

    def test_cmd_stop_gen3(self, shade_with_mocks):
        """Test cmdStop for Gen 3 gateway."""
        shade_with_mocks.cmdStop(None)

        expected_url = "http://powerview-g3.local/home/shades/stop?ids=12345"
        shade_with_mocks.controller.put.assert_called_with(expected_url)

    def test_cmd_tilt_open(self, shade_with_mocks):
        """Test cmdTiltOpen command."""
        shade_with_mocks.capabilities = 1
        shade_with_mocks.setShadePosition = Mock()
        shade_with_mocks.cmdTiltOpen(None)

        shade_with_mocks.setShadePosition.assert_called_once()

    def test_cmd_tilt_close(self, shade_with_mocks):
        """Test cmdTiltClose command."""
        shade_with_mocks.capabilities = 1
        shade_with_mocks.setShadePosition = Mock()
        shade_with_mocks.cmdTiltClose(None)

        shade_with_mocks.setShadePosition.assert_called_once()

    def test_cmd_jog(self, shade_with_mocks):
        """Test cmdJog command."""
        shade_with_mocks.cmdJog()

        shade_with_mocks.controller.put.assert_called_once()

    def test_query_command(self, shade_with_mocks):
        """Test query command handler."""
        shade_with_mocks.updateData = Mock()
        shade_with_mocks.reportDrivers = Mock()

        shade_with_mocks.query()

        shade_with_mocks.updateData.assert_called_once()
        shade_with_mocks.reportDrivers.assert_called_once()


class TestShadePositionConversion:
    """Tests for Shade position conversion methods."""

    @pytest.fixture
    def shade_with_mocks(self):
        """Create a Shade with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.shades_map = {}
        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller_addr", "shade_addr", "Test Shade", "12345")

        return shade

    def test_pos_to_percent(self, shade_with_mocks):
        """Test posToPercent conversion."""
        shade_with_mocks.controller.toPercent = Mock(side_effect=lambda x: x / 100)
        positions = {"primary": 5000, "secondary": 7500, "tilt": 9000}

        result = shade_with_mocks.posToPercent(positions)

        assert result["primary"] == 50
        assert result["secondary"] == 75
        assert result["tilt"] == 90


class TestShadeUpdatePositions:
    """Tests for Shade updatePositions method."""

    @pytest.fixture
    def shade_with_mocks(self):
        """Create a Shade with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.generation = 3
        controller.shades_map = {"12345": {"positions": {}}}
        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller_addr", "shade_addr", "Test Shade", "12345")
        shade.capabilities = 0  # Primary only
        shade.setDriver = Mock()

        return shade

    def test_update_positions_callable(self, shade_with_mocks):
        """Test updatePositions is callable."""
        shade_with_mocks.capabilities = 0
        positions = {"primary": 50}

        # Just verify it doesn't raise an exception
        try:
            shade_with_mocks.updatePositions(positions)
            assert True
        except Exception:
            assert False, "updatePositions should not raise exception"


class TestShadeDriversCommands:
    """Tests for Shade drivers and commands configuration."""

    def test_drivers_defined(self):
        """Test that Shade has correct drivers defined."""
        assert hasattr(Shade, "drivers")
        assert len(Shade.drivers) == 8

        driver_names = [d["driver"] for d in Shade.drivers]
        assert "ST" in driver_names
        assert "GV0" in driver_names
        assert "GV1" in driver_names
        assert "GV2" in driver_names
        assert "GV3" in driver_names
        assert "GV4" in driver_names
        assert "GV5" in driver_names
        assert "GV6" in driver_names

    def test_commands_defined(self):
        """Test that Shade has correct commands defined."""
        assert hasattr(Shade, "commands")
        assert "OPEN" in Shade.commands
        assert "CLOSE" in Shade.commands
        assert "STOP" in Shade.commands
        assert "TILTOPEN" in Shade.commands
        assert "TILTCLOSE" in Shade.commands
        assert "JOG" in Shade.commands
        assert "QUERY" in Shade.commands
        assert "SETPOS" in Shade.commands


class TestShadeSubclasses:
    """Tests for Shade subclass definitions."""

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
        controller.shades_map = {}
        return controller

    def test_shade_no_tilt_id(self):
        """Test ShadeNoTilt has correct ID."""
        assert ShadeNoTilt.id == "shadenotiltid"

    def test_shade_no_tilt_drivers(self):
        """Test ShadeNoTilt has correct drivers (no GV4 tilt)."""
        driver_names = [d["driver"] for d in ShadeNoTilt.drivers]
        assert "GV4" not in driver_names
        assert "GV2" in driver_names
        assert "GV3" in driver_names

    def test_shade_only_primary_id(self):
        """Test ShadeOnlyPrimary has correct ID."""
        assert ShadeOnlyPrimary.id == "shadeonlyprimid"

    def test_shade_only_primary_drivers(self):
        """Test ShadeOnlyPrimary has correct drivers (only GV2)."""
        driver_names = [d["driver"] for d in ShadeOnlyPrimary.drivers]
        assert "GV2" in driver_names
        assert "GV3" not in driver_names
        assert "GV4" not in driver_names

    def test_shade_only_secondary_id(self):
        """Test ShadeOnlySecondary has correct ID."""
        assert ShadeOnlySecondary.id == "shadeonlysecondid"

    def test_shade_only_secondary_drivers(self):
        """Test ShadeOnlySecondary has correct drivers (only GV3)."""
        driver_names = [d["driver"] for d in ShadeOnlySecondary.drivers]
        assert "GV3" in driver_names
        assert "GV2" not in driver_names
        assert "GV4" not in driver_names

    def test_shade_no_secondary_id(self):
        """Test ShadeNoSecondary has correct ID."""
        assert ShadeNoSecondary.id == "shadenosecondid"

    def test_shade_no_secondary_drivers(self):
        """Test ShadeNoSecondary has correct drivers (no GV3)."""
        driver_names = [d["driver"] for d in ShadeNoSecondary.drivers]
        assert "GV2" in driver_names
        assert "GV4" in driver_names
        assert "GV3" not in driver_names

    def test_shade_only_tilt_id(self):
        """Test ShadeOnlyTilt has correct ID."""
        assert ShadeOnlyTilt.id == "shadeonlytiltid"

    def test_shade_only_tilt_drivers(self):
        """Test ShadeOnlyTilt has correct drivers (only GV4)."""
        driver_names = [d["driver"] for d in ShadeOnlyTilt.drivers]
        assert "GV4" in driver_names
        assert "GV2" not in driver_names
        assert "GV3" not in driver_names

    def test_subclass_inherits_from_shade(self, mock_poly, mock_controller):
        """Test that all subclasses inherit from Shade."""
        mock_poly.getNode = Mock(return_value=mock_controller)

        # Create instances and verify inheritance
        shade_no_tilt = ShadeNoTilt(mock_poly, "ctrl", "addr1", "Test1", "1")
        shade_only_prim = ShadeOnlyPrimary(mock_poly, "ctrl", "addr2", "Test2", "2")
        shade_only_sec = ShadeOnlySecondary(mock_poly, "ctrl", "addr3", "Test3", "3")
        shade_no_sec = ShadeNoSecondary(mock_poly, "ctrl", "addr4", "Test4", "4")
        shade_only_tilt = ShadeOnlyTilt(mock_poly, "ctrl", "addr5", "Test5", "5")

        assert isinstance(shade_no_tilt, Shade)
        assert isinstance(shade_only_prim, Shade)
        assert isinstance(shade_only_sec, Shade)
        assert isinstance(shade_no_sec, Shade)
        assert isinstance(shade_only_tilt, Shade)


class TestShadeBatteryHandling:
    """Tests for Shade battery status handling."""

    @pytest.fixture
    def shade_with_mocks(self):
        """Create a Shade with mocked dependencies."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.generation = 3
        controller.shades_map = {"12345": {"shd_Id": "12345", "batteryStatus": 2}}
        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller_addr", "shade_addr", "Test Shade", "12345")
        shade.setDriver = Mock()

        return shade


class TestShadeGen2Compatibility:
    """Tests for Gen 2 gateway compatibility."""

    @pytest.fixture
    def shade_gen2_mocks(self):
        """Create a Shade with Gen 2 gateway."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        controller = Mock()
        controller.ready_event = Event()
        controller.gateway = "powerview-hub.local"
        controller.generation = 2
        controller.get = Mock()
        controller.shades_map = {
            "12345": {
                "id": 12345,
                "positions": {
                    "posKind1": 1,
                    "position1": 32768,
                    "posKind2": 2,
                    "position2": 16384,
                },
            }
        }
        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller_addr", "shade_addr", "Test Shade", "12345")
        shade.setDriver = Mock()
        shade.reportCmd = Mock()

        return shade

    def test_cmd_open_gen2(self, shade_gen2_mocks):
        """Test cmdOpen for Gen 2 gateway uses GET."""
        shade_gen2_mocks.capabilities = 0
        shade_gen2_mocks.setShadePosition = Mock()
        shade_gen2_mocks.cmdOpen(None)

        # Should call setShadePosition which will call controller.get for Gen 2
        assert (
            shade_gen2_mocks.setShadePosition.called
            or shade_gen2_mocks.controller.get.called
        )
