
import udi_interface

LOGGER = udi_interface.LOGGER

class Scene(udi_interface.Node):
    id = 'sceneid'

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
        :param sid: scene id
        """
        super(Scene, self).__init__(polyglot, primary, address, name)

        self.poly = polyglot
        self.primary = primary
        self.controller = polyglot.getNode(self.primary)
        self.address = address
        self.name = name

        self.lpfx = '%s:%s' % (address,name)
        self.sid = sid

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)

    def start(self):
        """
        Optional.
        This method is called after Polyglot has added the node per the
        START event subscription above
        """
        self.setDriver('ST', 0)
        LOGGER.debug('%s: get ST=%s',self.lpfx,self.getDriver('ST'))
        self.setDriver('GV0', int(self.sid))
        LOGGER.debug('%s: get GV0=%s',self.lpfx,self.getDriver('GV0'))

    def poll(self, flag):
        if 'longPoll' in flag:
            LOGGER.debug(f"longPoll {self.lpfx}")
        else:
            LOGGER.debug(f"shortPoll {self.lpfx}")
            event = list(filter(lambda events: (events['evt'] == 'scene-activated' or events['evt'] == 'scene-deactivated'), \
                                self.controller.gateway_event))
            if event:
                event = event[0]
                LOGGER.debug(f"shortpoll scene {self.sid} - {event['id']} - {event}")
                if int(event['id']) == int(self.sid):
                    act = event['evt'] == 'scene-activated'
                    if act:
                        self.setDriver('ST', 1)
                    else:
                        self.setDriver('ST', 0)
                    LOGGER.info(f"shortPoll {self.lpfx} activate = {act}")
                    self.controller.gateway_event.remove(event)
                
    def cmdActivate(self, command):
        """
        activate scene
        """
        self.controller.activateScene(self.sid)
        LOGGER.debug(f"cmdActivate initiate {self.lpfx}")

    def query(self, command = None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        self.reportDrivers()

    """
    This is an array of dictionary items containing the variable names(drivers)
    values and uoms(units of measure) from ISY. This is how ISY knows what kind
    of variable to display. Check the UOM's in the WSDK for a complete list.
    UOM 2 is boolean so the ISY will display 'True/False'
    """
    drivers = [
        {'driver': 'GV0', 'value': 0, 'uom': 25},
        {'driver': 'ST', 'value': 0, 'uom': 2},
               ]

    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
                    'ACTIVATE': cmdActivate,
                    'QUERY': query,
                }

