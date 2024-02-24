
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
        self.shadedata = {}
        self.positions = {}
        self.capabilities = 0

        self.lpfx = '%s:%s' % (address,name)
        self.sid = sid

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)
        
    def start(self):
        """
        This method is called after Polyglot has added the node per the
        START event subscription above
        """
        self.setDriver('GV0', self.sid)
        self.updateData()
        self.reportDrivers()

    def poll(self, flag):
        if 'longPoll' in flag:
            LOGGER.debug('longPoll (shade)')
        else:
            LOGGER.debug('shortPoll (shade)')

            # home update event
            event = list(filter(lambda events: events['evt'] == 'home', self.controller.gateway_event))
            if event:
                event = event[0]
                if event['shades'].count(self.sid) > 0:
                    LOGGER.info(f'shortPoll shade {self.sid} update')
                    if self.updateData():
                        self.controller.gateway_event[self.controller.gateway_event.index(event)]['shades'].remove(self.sid)
                else:
                    LOGGER.debug(f'shortPoll shade {self.sid} home evt but update already')
            else:
                LOGGER.debug(f'shortPoll shade {self.sid} no home evt')
                
            # motion-started event
            event = list(filter(lambda events: (events['evt'] == 'motion-started' and events['id'] == self.sid), \
                                self.controller.gateway_event))
            if event:
                event = event[0]
                self.positions = self.posToPercent(event['currentPositions'])
                if self.updatePositions(self.positions, self.capabilities):
                    self.setDriver('ST', 1)
                    LOGGER.info(f'shortPoll shade {self.sid} motion-started update')
                    self.controller.gateway_event.remove(event)
                   
            # motion-stopped event
            event = list(filter(lambda events: (events['evt'] == 'motion-stopped' and events['id'] == self.sid), \
                                self.controller.gateway_event))
            if event:
                event = event[0]
                self.positions = self.posToPercent(event['currentPositions'])
                if self.updatePositions(self.positions, self.capabilities):
                    self.setDriver('ST', 0)
                    LOGGER.info(f'shortPoll shade {self.sid} motion-stopped update')
                    self.controller.gateway_event.remove(event)
                   
            # shade-online event
            event = list(filter(lambda events: (events['evt'] == 'shade-online' and events['id'] == self.sid), \
                                self.controller.gateway_event))
            if event:
                event = event[0]
                self.positions = self.posToPercent(event['currentPositions'])
                if self.updatePositions(self.positions, self.capabilities):
                    LOGGER.info(f'shortPoll shade {self.sid} shade-online update')
                    self.controller.gateway_event.remove(event)
                   
    def updateData(self):
        if self.controller.no_update == False:
            LOGGER.debug(self.controller.shades_array)
            self.shadedata = list(filter(lambda shade: shade['id'] == self.sid, self.controller.shades_array))
            LOGGER.debug(f"shade {self.sid} is {self.shadedata}")
            if self.shadedata:
                self.shadedata = self.shadedata[0]
                self.setDriver('GV1', self.shadedata["roomId"])
                self.setDriver('GV6', self.shadedata["batteryStatus"])
                self.setDriver('GV5', self.shadedata["capabilities"])
                self.positions = self.shadedata["positions"]
                self.capabilities = int(self.shadedata["capabilities"])
                self.updatePositions(self.positions, self.capabilities)
                return True
        else:
            return False

    def updatePositions(self, positions, capabilities):
        if capabilities == 7 or capabilities == 8:
            self.setDriver('GV2', positions["primary"])
            self.setDriver('GV3', positions["secondary"])
            self.setDriver('GV4', None)
        elif capabilities == 0 or capabilities == 3:
            self.setDriver('GV2', positions["primary"])
            self.setDriver('GV3', None)
            self.setDriver('GV4', None)
        elif capabilities == 6:
            self.setDriver('GV2', None)
            self.setDriver('GV3', positions["secondary"])
            self.setDriver('GV4', None)
        elif capabilities == 1 or capabilities == 2 or capabilities == 4:
            self.setDriver('GV2', positions["primary"])
            self.setDriver('GV3', None)
            self.setDriver('GV4', positions["tilt"])
        # elif capabilities = 99: # not used
        #     self.setDriver('GV2', None)
        #     self.setDriver('GV3', positions["secondary"], force= True)
        #     self.setDriver('GV4', positions["tilt"], force= True)
        elif capabilities == 5:
            self.setDriver('GV2', None)
            self.setDriver('GV3', None)
            self.setDriver('GV4', positions["tilt"])
        else: # 9, 10 , unknown
            self.setDriver('GV2', positions["primary"])
            self.setDriver('GV3', positions["secondary"])
            self.setDriver('GV4', positions["tilt"])
        return True

    def posToPercent(self, pos):
        for key in pos:
            pos[key] = self.controller.toPercent(pos[key])
        return pos
        
    def cmdOpen(self, command):
        """
        open shade
        """
        LOGGER.debug('Shade Open %s', self.lpfx)
        self.positions["primary"] = 0
        self.controller.setShadePosition(self.sid, self.positions)

    def cmdClose(self, command):
        """
        close shade
        """
        LOGGER.debug('Shade Open %s', self.lpfx)
        self.positions["primary"] = 100
        self.controller.setShadePosition(self.sid, self.positions)

    def cmdStop(self, command):
        """
        stop shade
        """
        LOGGER.debug('Shade Stop %s', self.lpfx)
        self.controller.stopShade(self.sid)

    def cmdTiltOpen(self, command):
        """
        tilt shade open
        """
        LOGGER.debug('Shade TiltOpen %s', self.lpfx)
        self.positions["tilt"] = 50
        self.controller.setShadePosition(self.sid, self.positions)

    def cmdTiltClose(self, command):
        """
        tilt shade close
        """
        LOGGER.debug('Shade TiltClose %s', self.lpfx)
        self.positions["tilt"] = 0
        self.controller.setShadePosition(self.sid, self.positions)

    def cmdJog(self, command):
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
        self.updateData()
        self.reportDrivers()

    def cmdSetpos(self, command):
        """
        setting primary, secondary, tilt
        """
        try:
            LOGGER.info('Shade Setpos command %s', command)
            query = command.get("query")
            LOGGER.info('Shade Setpos query %s', query)
            self.positions["primary"] = int(query.get("SETPRIM.uom100"))
            self.positions["secondary"] = int(query.get("SETSECO.uom100"))
            self.positions["tilt"] = int(query.get("SETTILT.uom100"))
            LOGGER.info('Shade Setpos %s', self.positions)
            self.controller.setShadePosition(self.sid, self.positions)
        except:
            LOGGER.error('Shade Setpos failed %s', self.lpfx)


    """
        {'driver': 'GV0', 'value': 0, 'uom': 107}# id
        {'driver': 'ST', 'value': 0, 'uom': 2} # motion
        {'driver': 'GV1', 'value': 0, 'uom': 107}# room -> roomId
        {'driver': 'GV2', 'value': 0, 'uom': 79}# actual positions {primary}
        {'driver': 'GV3', 'value': 0, 'uom': 79}# actual positions {secondary}
        {'driver': 'GV4', 'value': 0, 'uom': 79}# actual positions {tilt}
        {'driver': 'GV5', 'value': 0, 'uom': 25}# capabilities
        {'driver': 'GV6', 'value': 0, 'uom': 25)# batteryStatus
    """

        # all the drivers - for reference
    drivers = [
        {'driver': 'GV0', 'value': 0, 'uom': 107, 'name': "Shade Id"},
        {'driver': 'ST', 'value': 0, 'uom': 2, 'name': "In Motion"}, 
        {'driver': 'GV1', 'value': 0, 'uom': 107, 'name': "Room Id"},
        {'driver': 'GV2', 'value': None, 'uom': 100, 'name': "Primary"},
        {'driver': 'GV3', 'value': None, 'uom': 100, 'name': "Secondary"},
        {'driver': 'GV4', 'value': None, 'uom': 100, 'name': "Tilt"},
        {'driver': 'GV5', 'value': 0, 'uom': 25, 'name': "Capabilities"},
        {'driver': 'GV6', 'value': 0, 'uom': 25, 'name': "Battery Status"},
        ]

    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
    'OPEN': cmdOpen,
    'CLOSE': cmdClose,
    'STOP': cmdStop,
    'TILTOPEN': cmdTiltOpen,
    'TILTCLOSE': cmdTiltClose,
    'JOG': cmdJog,
    'SETPOS': cmdSetpos,
    'QUERY': query,
    }
                   
