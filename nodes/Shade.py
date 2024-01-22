
import udi_interface

LOGGER = udi_interface.LOGGER

class Shade(udi_interface.Node):
    id = 'shadeid'
    
    """
    This is the class that all the Nodes will be represented by. You will
    add this to Polyglot/ISY with the interface.addNode method.

    Class Variables:
    self.primary: String address of the parent node.
    self.address: String address of this Node 14 character limit.
                  (ISY limitation)
    self.added: Boolean Confirmed added to ISY

    Class Methods:
    setDriver('ST', 1, report = True, force = False):
        This sets the driver 'ST' to 1. If report is False we do not report
        it to Polyglot/ISY. If force is True, we send a report even if the
        value hasn't changed.
    reportDriver(driver, force): report the driver value to Polyglot/ISY if
        it has changed.  if force is true, send regardless.
    reportDrivers(): Forces a full update of all drivers to Polyglot/ISY.
    query(): Called when ISY sends a query request to Polyglot for this
        specific node
    """
    def __init__(self, polyglot, primary, address, name, sid):
        """
        Optional.
        Super runs all the parent class necessities. You do NOT have
        to override the __init__ method, but if you do, you MUST call super.

        :param polyglot: Reference to the Interface class
        :param primary: Parent address
        :param address: This nodes address
        :param name: This nodes name
        """
        super(Shade, self).__init__(polyglot, primary, address, name)
        self.poly = polyglot
        self.primary = primary
        self.controller = polyglot.getNode(self.primary)
        self.address = address
        self.name = name

        self.lpfx = '%s:%s' % (address,name)
        self.sid = sid

        self.poly.subscribe(self.poly.START, self.start, address)

    def updatedata(self, updatefromserver = True):
        """
        update data
        """
        if updatefromserver:
            self.controller.updateAllFromServer()

        try:
            self.shadedata = self.controller.shades_array[self.controller.shadeIds_array.index(self.sid)]
            online = 1
            LOGGER.debug(self.shadedata)
        except:
            online = 0              
            LOGGER.debug('%s: OFFLINE',self.lpfx)
        finally:
            self.setDriver('ST', online)
            self.setDriver('GV0', self.shadedata["shadeId"])
            self.setDriver('GV3', self.shadedata["capabilities"])
            self.setDriver('GV5', self.shadedata["batteryStatus"])
            self.setDriver('GV6', self.shadedata["roomId"])
            self.setDriver('GV7', self.shadedata["positions"]["primary"])
            self.setDriver('GV8', self.shadedata["positions"]["secondary"])
            self.setDriver('GV9', self.shadedata["positions"]["tilt"])
            self.positions = self.shadedata["positions"]
        # self.positions = {"primary": 0, "secondary": 0, "tilt": 0, "velocity": 0}
        

    def start(self):
        """
        This method is called after Polyglot has added the node per the
        START event subscription above
        """
        self.updatedata(updatefromserver = False)

    def cmd_open(self, command):
        """
        open shade
        """
        LOGGER.debug('Shade Open %s', self.lpfx)
        self.positions["primary"] = 0
        self.controller.setShadePosition(self.sid, self.positions)

    def cmd_close(self, command):
        """
        close shade
        """
        LOGGER.debug('Shade Open %s', self.lpfx)
        self.positions["primary"] = 100
        self.controller.setShadePosition(self.sid, self.positions)

    def cmd_stop(self, command):
        """
        stop shade
        """
        LOGGER.debug('Shade Stop %s', self.lpfx)
        self.controller.stopShade(self.sid)


    def cmd_tiltopen(self, command):
        """
        tilt shade open
        """
        self.positions["tilt"] = 50
        self.controller.setShadePosition(self.sid, self.positions)

    def cmd_tiltclose(self, command):
        """
        tilt shade close
        """
        self.positions["tilt"] = 0
        self.controller.setShadePosition(self.sid, self.positions)

    def cmd_jog(self, command):
        """
        jog shade
        """
        LOGGER.debug('Shade JOG %s', self.lpfx)
        self.controller.jogShade(self.sid)

    def query(self, command=None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        self.updatedata(updatefromserver = True)
        self.reportDrivers()

    """
        {'driver': 'ST', 'value': 0, 'uom': 2} # online
        {'driver': 'GV0', 'value': 0, 'uom': 25}# id
        {'driver': 'GV3', 'value': 0, 'uom': 25}# capabilities
        {'driver': 'GV5', 'value': 0, 'uom': 25)# batteryStatus
        {'driver': 'GV6', 'value': 0, 'uom': 25}# room -> roomId
        {'driver': 'GV7', 'value': 0, 'uom': 25}# positions {primary, secondary, tilt}
        {'driver': 'GV8', 'value': 0, 'uom': 25}# positions {primary, secondary, tilt}
        {'driver': 'GV9', 'value': 0, 'uom': 25}# positions {primary, secondary, tilt}
    """
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 2}, 
        {'driver': 'GV0', 'value': 0, 'uom': 25},
        {'driver': 'GV3', 'value': 0, 'uom': 25},
        {'driver': 'GV5', 'value': 0, 'uom': 25},
        {'driver': 'GV6', 'value': 0, 'uom': 25},
        {'driver': 'GV7', 'value': 0, 'uom': 25},
        {'driver': 'GV8', 'value': 0, 'uom': 25},
        {'driver': 'GV9', 'value': 0, 'uom': 25},
               ]

    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
                    'OPEN': cmd_open,
                    'CLOSE': cmd_close,
                    'STOP': cmd_stop,
                    'TILTOPEN': cmd_tiltopen,
                    'TILTCLOSE': cmd_tiltclose,
                    'JOG': cmd_jog,
                    'QUERY': query,
                }

