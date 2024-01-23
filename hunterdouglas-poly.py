#!/usr/bin/env python3
"""
This is a Plugin/NodeServer for Polyglot v3 written in Python3
modified from v3 template version by (Bob Paauwe) bpaauwe@yahoo.com
It is an interface between HunterDouglas Shades and Polyglot for EISY/Polisy

(c) 2024 Stephen Jenkins
"""
import udi_interface
import sys

LOGGER = udi_interface.LOGGER

VERSION = '0.0.5'
"""
0.0.5:
DONE change shortpoll to 30s
DONE update shades on shortpoll
DONE clear start notice at shortpoll
DONE clean up error proofing in get
DONE fix updating variables with shortpoll
DONE limit device ping to 5s

add to future version:
TODO think about status updates when command is given
TODO move shade by specific amounts
TODO version update notices ; are they provided by polyglot now?
TODO remove parameters based on shade capability (primary, secondary, tilt)

past versions:
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
