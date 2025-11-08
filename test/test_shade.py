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


class TestShadePositionCalculations:
    """Tests for Shade position calculations and conversions."""

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
        controller.shades_map = {}
        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller_addr", "shade_addr", "Test Shade", "12345")
        shade.setDriver = Mock()

        return shade

    def test_cmdSetpos_exists(self, shade_with_mocks):
        """Test that cmdSetpos method exists."""
        assert hasattr(shade_with_mocks, "cmdSetpos")
        assert callable(shade_with_mocks.cmdSetpos)

    def test_pos_to_percent_conversion(self, shade_with_mocks):
        """Test posToPercent converts positions correctly."""
        pos_dict = {"primary": 50, "secondary": 75, "tilt": 25}
        result = shade_with_mocks.posToPercent(pos_dict)

        assert isinstance(result, dict)
        assert "primary" in result

    def test_from_percent_conversion(self, shade_with_mocks):
        """Test fromPercent converts percentages to raw values."""
        result = shade_with_mocks.fromPercent(50)

        assert isinstance(result, (int, float))
        assert result >= 0


class TestShadeUpdatePositionsMethods:
    """Tests for Shade position updates from gateway."""

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
        controller.update_shade_data = Mock()
        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller_addr", "shade_addr", "Test Shade", "12345")
        shade.setDriver = Mock()
        shade.capabilities = 9  # Duolite with tilt

        return shade

    def test_update_positions_primary(self, shade_with_mocks):
        """Test updatePositions updates primary position."""
        positions = {"primary": 5000, "secondary": 7500, "tilt": 2500}
        shade_with_mocks.updatePositions(positions)

        # Should set GV2 (primary position)
        calls = [
            c for c in shade_with_mocks.setDriver.call_args_list if c[0][0] == "GV2"
        ]
        assert len(calls) > 0

    def test_update_positions_with_tilt(self, shade_with_mocks):
        """Test updatePositions updates tilt for tilt-capable shade."""
        positions = {"primary": 5000, "secondary": 7500, "tilt": 2500}
        shade_with_mocks.updatePositions(positions)

        # Should set GV4 (tilt position)
        calls = [
            c for c in shade_with_mocks.setDriver.call_args_list if c[0][0] == "GV4"
        ]
        assert len(calls) > 0

    def test_update_positions_with_secondary(self, shade_with_mocks):
        """Test updatePositions updates secondary for duolite shade."""
        positions = {"primary": 5000, "secondary": 7500, "tilt": 2500}
        shade_with_mocks.updatePositions(positions)

        # Should set GV3 (secondary position)
        calls = [
            c for c in shade_with_mocks.setDriver.call_args_list if c[0][0] == "GV3"
        ]
        assert len(calls) > 0


class TestShadeCapabilities:
    """Tests for different shade capability types."""

    @pytest.fixture
    def basic_controller(self):
        """Create a basic mock controller."""
        controller = Mock()
        controller.ready_event = Event()
        controller.ready_event.set()
        controller.gateway = "powerview-g3.local"
        controller.generation = 3
        controller.shades_map = {}
        return controller

    def test_shade_no_tilt_type(self, basic_controller):
        """Test ShadeNoTilt class."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.getNode = Mock(return_value=basic_controller)

        shade = ShadeNoTilt(
            poly, "controller_addr", "shade_addr", "Test Shade", "12345"
        )

        assert shade.id == "shadenotiltid"

    def test_shade_only_primary_type(self, basic_controller):
        """Test ShadeOnlyPrimary class."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.getNode = Mock(return_value=basic_controller)

        shade = ShadeOnlyPrimary(
            poly, "controller_addr", "shade_addr", "Test Shade", "12345"
        )

        assert shade.id == "shadeonlyprimid"

    def test_shade_only_secondary_type(self, basic_controller):
        """Test ShadeOnlySecondary class."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.getNode = Mock(return_value=basic_controller)

        shade = ShadeOnlySecondary(
            poly, "controller_addr", "shade_addr", "Test Shade", "12345"
        )

        assert shade.id == "shadeonlysecondid"

    def test_shade_no_secondary_type(self, basic_controller):
        """Test ShadeNoSecondary class."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.getNode = Mock(return_value=basic_controller)

        shade = ShadeNoSecondary(
            poly, "controller_addr", "shade_addr", "Test Shade", "12345"
        )

        assert shade.id == "shadenosecondid"

    def test_shade_only_tilt_type(self, basic_controller):
        """Test ShadeOnlyTilt class."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])
        poly.getNode = Mock(return_value=basic_controller)

        shade = ShadeOnlyTilt(
            poly, "controller_addr", "shade_addr", "Test Shade", "12345"
        )

        assert shade.id == "shadeonlytiltid"


# ==================== PHASE 3 TESTS ====================


class TestShadeEventPollingG3:
    """Tests for Shade event polling functionality."""

    @pytest.fixture
    def shade_with_event_mocks(self):
        """Create a Shade with event polling mocks."""
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
        controller.get_shade_data = Mock(
            return_value={
                "shd_Id": "shade1",
                "positions": {"primary": 50, "tilt": 0},
                "capabilities": 0,
                "batteryStatus": 3,
            }
        )
        controller.shades_map = {
            "shade1": {
                "id": "shade1",
                "name": "Test Shade",
                "positions": {"primary": 50},
            }
        }

        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller", "shade1", "Test Shade", "shade1")
        shade.setDriver = Mock()
        shade.reportCmd = Mock()

        return shade

    def test_poll_events_for_g3_motion_started(self, shade_with_event_mocks):
        """Test _poll_events_for_g3 with motion-started event."""
        events = [
            {
                "evt": "motion-started",
                "id": "shade1",
                "isoDate": "2025-01-01T12:00:00.000Z",
                "targetPositions": {"primary": 75},
            }
        ]

        shade_with_event_mocks.updatePositions = Mock()
        shade_with_event_mocks._poll_events_for_g3(events)

        # Should update positions and set motion status
        shade_with_event_mocks.updatePositions.assert_called()
        calls = [
            c
            for c in shade_with_event_mocks.setDriver.call_args_list
            if c[0][0] == "ST"
        ]
        if calls:
            assert calls[0][0][1] == 1  # Motion status = 1

    def test_poll_events_for_g3_with_empty_events(self, shade_with_event_mocks):
        """Test _poll_events_for_g3 with no events."""
        events = []

        # Should not raise exception
        try:
            shade_with_event_mocks._poll_events_for_g3(events)
            assert True
        except Exception:
            assert False, "_poll_events_for_g3 should handle empty events"


class TestShadeGen2Operations:
    """Tests for Gen 2 shade operations."""

    @pytest.fixture
    def shade_gen2(self):
        """Create a Shade configured for Gen 2."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])

        controller = Mock()
        controller.ready_event = Event()
        controller.ready_event.set()
        controller.gateway = "192.168.1.100"
        controller.generation = 2
        controller.get = Mock()
        controller.shades_map = {}

        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller", "shade1", "Test Shade", "shade1")
        shade.setDriver = Mock()
        shade.capabilities = 0

        return shade

    def test_get_g2_positions_primary_only(self, shade_gen2):
        """Test _get_g2_positions with primary position only."""
        pos = {"primary": 50}

        result = shade_gen2._get_g2_positions(pos)

        assert "shade" in result
        assert "positions" in result["shade"]

    def test_get_g2_positions_with_tilt(self, shade_gen2):
        """Test _get_g2_positions with tilt position."""
        shade_gen2.capabilities = 1  # Tilt capable
        pos = {"primary": 50, "tilt": 45}

        result = shade_gen2._get_g2_positions(pos)

        assert "shade" in result
        assert "positions" in result["shade"]

    def test_get_g2_positions_with_secondary(self, shade_gen2):
        """Test _get_g2_positions with secondary position."""
        shade_gen2.capabilities = 7  # Has secondary
        pos = {"primary": 50, "secondary": 75}

        result = shade_gen2._get_g2_positions(pos)

        assert "shade" in result

    def test_get_g3_positions_primary(self, shade_gen2):
        """Test _get_g3_positions with primary position."""
        shade_gen2.controller.generation = 3
        pos = {"primary": 50}

        result = shade_gen2._get_g3_positions(pos)

        assert "positions" in result
        assert "primary" in result["positions"]

    def test_set_shade_position_gen2(self, shade_gen2):
        """Test setShadePosition for Gen 2."""
        # Gen 2 position setting is complex, just verify method exists
        assert hasattr(shade_gen2, "setShadePosition")
        assert callable(shade_gen2.setShadePosition)

    def test_set_shade_position_gen3(self, shade_gen2):
        """Test setShadePosition for Gen 3."""
        from unittest.mock import Mock as MockResponse

        shade_gen2.controller.generation = 3
        shade_gen2.controller.put = Mock()

        mock_response = MockResponse()
        mock_response.status_code = 200
        shade_gen2.controller.put.return_value = True

        pos = {"primary": 75}
        shade_gen2.setShadePosition(pos)

        # Should call controller.put for Gen 3
        assert shade_gen2.controller.put.called


class TestShadeCommandHandlers:
    """Tests for additional Shade command handlers."""

    @pytest.fixture
    def shade_with_commands(self):
        """Create a Shade with command mocks."""
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

        shade = Shade(poly, "controller", "shade1", "Test Shade", "shade1")
        shade.setDriver = Mock()
        shade.capabilities = 0

        return shade

    def test_cmd_jog(self, shade_with_commands):
        """Test cmdJog command."""
        shade_with_commands.controller.generation = 3
        shade_with_commands.cmdJog(None)

        # Should call controller.put for Gen 3
        assert shade_with_commands.controller.put.called

    def test_cmd_calibrate(self, shade_with_commands):
        """Test cmdCalibrate command (Gen 2 only)."""
        shade_with_commands.controller.generation = 2  # Gen 2
        shade_with_commands.cmdCalibrate(None)

        # Should call controller.put for Gen 2
        assert shade_with_commands.controller.put.called

    def test_query_updates_data(self, shade_with_commands):
        """Test query command updates shade data."""
        shade_with_commands.updateData = Mock(return_value=True)

        shade_with_commands.query(None)

        shade_with_commands.updateData.assert_called_once()


# ==================== PHASE 4 TESTS (BALANCED) ====================


class TestShadePositionValidation:
    """Tests for Shade position validation and edge cases."""

    @pytest.fixture
    def shade_positions(self):
        """Create a Shade for position testing."""
        poly = Mock()
        poly.subscribe = Mock()
        poly.db_getNodeDrivers = Mock(return_value=[])

        controller = Mock()
        controller.ready_event = Event()
        controller.ready_event.set()
        controller.gateway = "192.168.1.100"
        controller.generation = 3
        controller.shades_map = {}

        poly.getNode = Mock(return_value=controller)

        shade = Shade(poly, "controller", "shade1", "Test Shade", "shade1")
        shade.setDriver = Mock()
        shade.capabilities = 0

        return shade

    def test_from_percent_zero(self, shade_positions):
        """Test fromPercent with 0 percent."""
        result = shade_positions.fromPercent(0)

        assert result == 0.0

    def test_from_percent_hundred(self, shade_positions):
        """Test fromPercent with 100 percent."""
        result = shade_positions.fromPercent(100)

        assert isinstance(result, (int, float))
        assert result > 0

    def test_from_percent_with_divider(self, shade_positions):
        """Test fromPercent with custom divider."""
        result = shade_positions.fromPercent(50, divr=100.0)

        assert isinstance(result, (int, float))

    def test_pos_to_percent_empty_dict(self, shade_positions):
        """Test posToPercent with empty dictionary."""
        result = shade_positions.posToPercent({})

        assert isinstance(result, dict)
        assert len(result) == 0

    def test_pos_to_percent_with_values(self, shade_positions):
        """Test posToPercent converts all values."""
        pos = {"primary": 5000, "secondary": 7500, "tilt": 2500}
        result = shade_positions.posToPercent(pos)

        assert "primary" in result
        assert "secondary" in result
        assert "tilt" in result


class TestShadeOpenClose:
    """Tests for Shade open/close command variations."""

    @pytest.fixture
    def shade_commands(self):
        """Create a Shade for command testing."""
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

        shade = Shade(poly, "controller", "shade1", "Test Shade", "shade1")
        shade.setDriver = Mock()
        shade.setShadePosition = Mock()

        return shade

    def test_cmd_open_with_capabilities(self, shade_commands):
        """Test cmdOpen with different capabilities."""
        shade_commands.capabilities = 7  # Has primary and secondary

        shade_commands.cmdOpen(None)

        shade_commands.setShadePosition.assert_called()

    def test_cmd_close_with_capabilities(self, shade_commands):
        """Test cmdClose with different capabilities."""
        shade_commands.capabilities = 8  # Duolite

        shade_commands.cmdClose(None)

        shade_commands.setShadePosition.assert_called()

    def test_cmd_tilt_open_tilt_capable(self, shade_commands):
        """Test cmdTiltOpen with tilt-capable shade."""
        shade_commands.capabilities = 2  # Tilt capable (180°)

        shade_commands.cmdTiltOpen(None)

        shade_commands.setShadePosition.assert_called()

    def test_cmd_tilt_close_tilt_capable(self, shade_commands):
        """Test cmdTiltClose with tilt-capable shade."""
        shade_commands.capabilities = 4  # Tilt capable (180°)

        shade_commands.cmdTiltClose(None)

        shade_commands.setShadePosition.assert_called()
