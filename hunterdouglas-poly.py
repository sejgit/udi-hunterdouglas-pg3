#!/usr/bin/env python3
"""
This is a Plugin/NodeServer for Polyglot v3 written in Python3
modified from v3 template version by (Bob Paauwe) bpaauwe@yahoo.com
It is an interface between HunterDouglas Shades and Polyglot for EISY/Polisy
2024 Stephen Jenkins
"""
import udi_interface
import sys
"""
Import the polyglot interface module. This is in pypy so you can just install it
normally. Replace pip with pip3 if you are using python3.

Virtualenv:
pip install udi_interface

Not Virutalenv:
pip install udi_interface --user

* It is recommended you ALWAYS develop your NodeServers in virtualenv
  to maintain cleanliness, however that isn't required. Keep track of any
  other modules you install and add these to the requirements.txt file.
"""

"""
udi_interface has a LOGGER that is created by default and logs to:
  logs/debug.log
You can use LOGGER.info, LOGGER.warning, LOGGER.debug, LOGGER.error,
LOGGER.critical levels as needed in your node server.
"""
LOGGER = udi_interface.LOGGER

VERSION = '0.0.1'

""" Grab My Controller Node (optional) """
from nodes import Controller

if __name__ == "__main__":
    try:
        """
        Instantiates the Interface to Polyglot.

        * Optionally pass list of class names
          - PG2 had the controller node name here
        """
        polyglot = udi_interface.Interface([Controller])
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
