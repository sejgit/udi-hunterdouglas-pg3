#!/usr/bin/env python3
"""
This is a Plugin/NodeServer for Polyglot v3 written in Python3
modified from v3 template version by (Bob Paauwe) bpaauwe@yahoo.com
It is an interface between HunterDouglas Shades and Polyglot for EISY/Polisy

udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

main loop
"""

# std libraries
import sys

# external libraries
from udi_interface import Interface, LOGGER
from nodes import Controller


VERSION = "1.13.5"
"""
1.13.5
DONE sync versionHistory.md with hunterdouglas-poly.py; older history in versionHistory.md only
DONE fix ready_event poll checks (Controller, Shade, Scene)
DONE fix updateAllFromServer throttling and in-progress guard
DONE fix parameterHandler startup flag after checkParams
DONE replace eval() with json/ast parsing for gatewayip list
DONE accept gateway hostnames in addition to IP addresses
DONE thread-safe stale gateway event cleanup
DONE reset controller event_polling_in on thread exit
DONE add HTTP GET timeout to match PUT
DONE G3 shade discovery sets roomId and default batteryStatus
DONE Shade updateData null guards for missing shade data
DONE fix battery-alert event batteryLevel key handling
DONE fix Scene Gen2 active check (generation not gateway IP)
DONE safe scene-deactivated remove from sceneIdsActive
DONE consolidate PowerView URL constants into utils/urls.py
DONE consolidate gateway event lookup helpers in utils/gateway_events.py
DONE shared start_event_poll_thread helper for node event polling
DONE fix start_event_poll_thread when called from Controller
DONE get_gateway_event wait timeout so pollers cannot block indefinitely
DONE SSE Not Found handling restarts stream without stopping node pollers
DONE G2 updateAllFromServerG2 fails if rooms/shades/scenes fetch fails

1.13.4
DONE package updates "dependabot"

1.13.3
DONE package updates "dependabot"
DONE fix typo, crash on batteryLevel event
DONE fix timeout, drop every 300s timeout

1.13.2
DONE requirements.txt changes
DONE comments improvements
DONE testing additions

1.13.1
DONE refactor controller discovery, put, get, goodip functions
DONE refactor controller startup, config, params, naming, logging
DONE refactor cmdSetPos

1.13.0
DONE polling rewrite, controller: shortPoll=G2 poll, heartbeat for all, re-start G3 events, longPoll=G3 poll
DONE polling rewrite, shade: shortPoll: re-start events if stopped, longPoll: not-used
DONE polling rewrite, scene: shortPoll: re-start events if stopped, manually clear G2 scene activate, longPoll: not-used
NOTE default & recommend setting shortPoll=60, longPoll=600
DONE major re-write of function and Event routines
DONE add number of nodes managed by controller to controller node

for previous versions see versionHistory.md

"""


def main():
    polyglot = None
    try:
        """
        Instantiates the Interface to Polyglot.

        * Optionally pass list of class names
          - PG2 had the controller node name here
        """
        polyglot = Interface([])
        """
        Starts MQTT and connects to Polyglot.
        """
        polyglot.start(VERSION)

        """
        Creates the Controller Node and passes in the Interface, the node's
        parent address, node's address, and name/title

        * address, parent address, and name/title are new for Polyglot
          version 3
        * use 'controller' for both parent and address and PG3 will be able
          to automatically update node server status
        """
        control = Controller(polyglot, "hdctrl", "hdctrl", "HunterDouglas")
        LOGGER.debug(f"Controller:{control}")

        """
        Sits around and does nothing forever, keeping your program running.

        * runForever() moved from controller class to interface class in
          Polyglot version 3
        """
        polyglot.runForever()
    except (KeyboardInterrupt, SystemExit):
        LOGGER.warning("Received interrupt or exit...")
        """
        Catch SIGTERM or Control-C and exit cleanly.
        """
        if polyglot is not None:
            polyglot.stop()
        sys.exit(0)
    except Exception as err:
        LOGGER.error(f"Excption: {err}", exc_info=True)
        sys.exit(0)


if __name__ == "__main__":
    main()
