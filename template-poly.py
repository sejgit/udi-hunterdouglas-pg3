#!/usr/bin/env python
"""
This is a NodeServer template for Polyglot v3 written in Python3
v2 version by Einstein.42 (James Milne) milne.james@gmail.com
v3 version by (Bob Paauwe) bpaauwe@yahoo.com
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

*I recommend you ALWAYS develop your NodeServers in virtualenv to maintain
cleanliness, however that isn't required. I do not condone installing pip
modules globally. Use the --user flag, not sudo.
"""
LOGGER = udi_interface.LOGGER
"""
udi_interface has a LOGGER that is created by default and logs to:
logs/debug.log
You can use LOGGER.info, LOGGER.warning, LOGGER.debug, LOGGER.error levels as needed.
"""

""" Grab My Controller Node """
from nodes import TemplateController

if __name__ == "__main__":
    try:
        """
        Instantiates the Interface to Polyglot.

        *pass list of class names instead of a node name for Polyglot version 3
        """
        polyglot = udi_interface.Interface([TemplateController])
        polyglot.start()
        """
        Starts MQTT and connects to Polyglot.
        """
        control = TemplateController(polyglot, 'controller', 'controller', 'PythonTemplate')
        """
        Creates the Controller Node and passes in the Interface, the node's address,
        parent address, and name/title.  

        *address, parent address, and name/title are new for Polyglot version 3
        """
        polyglot.runForever()
        """
        Sits around and does nothing forever, keeping your program running.

        *runForever() moved from controller class to interface class in Polyglot version 3
        """
    except (KeyboardInterrupt, SystemExit):
        LOGGER.warning("Received interrupt or exit...")
        """
        Catch SIGTERM or Control-C and exit cleanly.
        """
        polyglot.stop()
    except Exception as err:
        LOGGER.error('Excption: {0}'.format(err), exc_info=True)
    sys.exit(0)
