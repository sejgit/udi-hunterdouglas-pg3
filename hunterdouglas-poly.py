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


VERSION = '1.13.1'
"""
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

1.12.8
DONE prevent update until previous complete
DONE update README with 120s LongPoll suggestion for G3 due to Events updates
NEXT minor change, don't push to production until other changes needed

1.12.7
DEBUG crash when connection reset by peer ; fix data
DONE remove separate open / close behaviour for G2/G3

1.12.6
DONE reverse open / close behaviour for G3 shades

1.12.5
DONE re-write SSE for G3
DONE fix motion if motion-stop missed
DONE battery low event added for G3
DONE force updates to server (helps with new eisy-ui)
DONE doc clean-up
DONE string clean-up
DONE improve logging
DONE bumped requests and urllib3 versions

1.12.4
DEBUG Gen-2 make a default capability if none exists in JSON

1.12.3
DONE G2 Scene event fix

1.12.2
DONE add shade-offline event handling to error log; currently not passed to ISY
DONE add updating of scene activation status on longPoll as backup to event

1.12.1
DONE environment updates
DONE small refactors

1.12.0
DONE change versioning to align with workflow
DONE update docs: README, versionHistory, logging

for previous version see versionHistory.md

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
        control = Controller(polyglot, 'hdctrl', 'hdctrl', 'HunterDouglas')
        LOGGER.debug(f'Controller:{control}')

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
        LOGGER.error(f'Excption: {err}', exc_info=True)
        sys.exit(0)

    
if __name__ == "__main__":
    main()
