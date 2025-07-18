#!/usr/bin/env python3
"""
This is a Plugin/NodeServer for Polyglot v3 written in Python3
modified from v3 template version by (Bob Paauwe) bpaauwe@yahoo.com
It is an interface between HunterDouglas Shades and Polyglot for EISY/Polisy

udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

main loop
"""

# std libraries
import sys

# external libraries
import udi_interface

LOGGER = udi_interface.LOGGER

VERSION = '1.12.5'
"""
1.12.5
DONE Some doc clean-up
DONE Some string clean-up
TODO Make more robust to controller faults

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

from nodes import Controller

if __name__ == "__main__":
    try:
        """
        Instantiates the Interface to Polyglot.

        * Optionally pass list of class names
          - PG2 had the controller node name here
        """
        polyglot = udi_interface.Interface([])
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
        polyglot.stop()
    except Exception as err:
        LOGGER.error('Excption: {0}'.format(err), exc_info=True)
    sys.exit(0)
