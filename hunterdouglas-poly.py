#!/usr/bin/env python3
"""
This is a Plugin/NodeServer for Polyglot v3 written in Python3
modified from v3 template version by (Bob Paauwe) bpaauwe@yahoo.com
It is an interface between HunterDouglas Shades and Polyglot for EISY/Polisy

udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

main loop
"""

import udi_interface
import sys

LOGGER = udi_interface.LOGGER

VERSION = '0.1.6'
"""
0.1.6
DONE parameters based on shade capabilities

past versions:
0.1.5
DONE format for program setShadePosition
DONE set Shade Position change using False to define which parameters to change
DONE more debug on G2 so it acts as expected

0.1.4
DONE add node_queue & as result need pause updates while in discovery
DONE FIRST TRY G2 tilt feature

0.1.3
DONE node discover rewrite to allow add/remove
DONE add event 'homedoc-updated' currently no actions
DONE limit room label size to 15 as room - shade/scene < 30 for ISY
DONE clean up LOGGING.debug messages
DONE G2 bug fixes

0.1.2
DONE change icons to nicer ones
DONE docs with screenshots & description for udi spotlight
DONE add troubleshooting document
DONE add some support for G2 gateways (no gateway push, only polling)

0.1.1
DONE tap into gateway events, which allows longPoll update to move from 30s to 60s
DONE active scene indications from events
DONE shade motion indicator from events
DONE shade position update from start, stop, online events
DONE remove parameters based on shade capability (primary, secondary, tilt)
DONE update readme & config instructions to highlight G3 scope

0.1.0
DONE handle multiple gateways automatically, picking primary & switching if required
DONE updated configuration instructions as well as link to the forums

0.0.9
DONE fix uom for positions(100) & ids(107)
DONE more notices clean-up
DONE shade naming to include room as scenes
DONE remove status based on shade capability (primary, secondary, tilt)

0.0.8:
DONE handling of notices individually
DONE polling 5s short-poll 30s long-poll
DONE status for programs (positions etc)

0.0.7:
DONE faster status updates when command is given
DONE bug fix
DONE re-order of parameters displayed

0.0.6:
DONE move shade by specific amounts
DONE bug fix scenes not activating

0.0.5:
DONE change shortpoll to 30s
DONE update shades on shortpoll
DONE clear start notice at shortpoll
DONE clean up error proofing in get
DONE fix updating variables with shortpoll
DONE limit device ping to 5s

0.0.4:
DONE discover when new gatewayip is entered
DONE poll status regularly using shortpoll
DONE update required after nodes added to get status
DONE notice when gateway get error
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
