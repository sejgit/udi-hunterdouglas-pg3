
"""
udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

Shade class
"""

import udi_interface
import math

LOGGER = udi_interface.LOGGER

"""
HunterDouglas PowerView G3 url's
"""
URL_DEFAULT_GATEWAY = 'powerview-g3.local'
URL_GATEWAY = 'http://{g}/gateway'
URL_HOME = 'http://{g}/home'
URL_ROOMS = 'http://{g}/home/rooms/{id}'
URL_SHADES = 'http://{g}/home/shades/{id}'
URL_SHADES_MOTION = 'http://{g}/home/shades/{id}/motion'
URL_SHADES_POSITIONS = 'http://{g}/home/shades/positions?ids={id}'
URL_SHADES_STOP = 'http://{g}/home/shades/stop?ids={id}'
URL_SCENES = 'http://{g}/home/scenes/{id}'
URL_SCENES_ACTIVATE = 'http://{g}/home/scenes/{id}/activate'
URL_EVENTS = 'http://{g}/home/events'
URL_EVENTS_SCENES = 'http://{g}/home/scenes/events'
URL_EVENTS_SHADES = 'http://{g}/home/shades/events'

"""
HunterDouglas PowerView G2 url's
from api file: [[https://github.com/sejgit/indigo-powerview/blob/master/PowerViewG2api.md]]
"""
URL_G2_HUB = 'http://{g}/api/userdata/'
URL_G2_ROOMS = 'http://{g}/api/rooms'
URL_G2_ROOM = 'http://{g}/api/rooms/{id}'
URL_G2_SHADES = 'http://{g}/api/shades'
URL_G2_SHADE = 'http://{g}/api/shade/{id}'
URL_G2_SHADE_BATTERY = 'http://{g}/api/shades/{id}?updateBatteryLevel=true'
URL_G2_SCENES = 'http://{g}/api/scenes'
URL_G2_SCENE = 'http://{g}/api/scenes?sceneid={id}'
URL_G2_SCENES_ACTIVATE = 'http://{g}/api/scenes?sceneid={id}'
G2_DIVR = 65535

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
        super().__init__(polyglot, primary, address, name)
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
            # LOGGER.debug('shortPoll (shade)')
            self.events()

    def events(self):
        # home update event
        event = list(filter(lambda events: events['evt'] == 'home', self.controller.gateway_event))
        if event:
            event = event[0]
            if event['shades'].count(self.sid) > 0:
                LOGGER.info(f'shortPoll shade {self.sid} update')
                if self.updateData():
                    try:
                        self.controller.gateway_event[self.controller.gateway_event.index(event)]['shades'].remove(self.sid)
                    except:
                        LOGGER.error(f"shade event error sid = {self.sid}")
            else:
                pass
                # LOGGER.debug(f'shortPoll shade {self.sid} home evt but update already')
        else:
            pass
            # LOGGER.debug(f'shortPoll shade {self.sid} no home evt')

        # NOTE rest of the events below are only for G3, will not fire for G2

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
            # LOGGER.debug(self.controller.shades_array)
            data = list(filter(lambda shade: shade['id'] == self.sid, self.controller.shades_array))
            LOGGER.debug(f"shade {self.sid} is {data}")
            if data:
                self.shadedata = data[0]
                self.setDriver('GV1', self.shadedata["roomId"])
                self.setDriver('GV6', self.shadedata["batteryStatus"])
                self.setDriver('GV5', self.shadedata["capabilities"])
                self.capabilities = int(self.shadedata["capabilities"])
                self.positions = self.shadedata["positions"]
                self.updatePositions(self.positions, self.capabilities)
                return True
        else:
            return False

    def updatePositions(self, positions, capabilities):
        if self.controller.generation == 2:
            if 'position1' in positions:
                p1 = positions['position1']
            else:
                p1 = None
            if 'position2' in positions:
                p2 = positions['position2']
            else:
                p2 = None
            t1 = None
        else:
            if 'primary' in positions:
                p1 = positions['primary']
            else:
                p1 = None
            if 'secondary' in positions:
                p2 = positions['secondary']
            else:
                p2 = None
            if 'tilt' in positions:
                t1 = positions['tilt']
            else:
                t1 = None
        LOGGER.debug(f"updatePositions {p1} {p2} {t1}")
            
        if capabilities == 7 or capabilities == 8:
            self.setDriver('GV2', p1)
            self.setDriver('GV3', p2)
            self.setDriver('GV4', None)
        elif capabilities == 0 or capabilities == 3:
            self.setDriver('GV2', p1)
            self.setDriver('GV3', None)
            self.setDriver('GV4', None)
        elif capabilities == 6:
            self.setDriver('GV2', None)
            self.setDriver('GV3', p2)
            self.setDriver('GV4', None)
        elif capabilities == 1 or capabilities == 2 or capabilities == 4:
            self.setDriver('GV2', p1)
            self.setDriver('GV3', None)
            self.setDriver('GV4', t1)
        # elif capabilities = 99: # not used
        #     self.setDriver('GV2', None)
        #     self.setDriver('GV3', positions["secondary"], force= True)
        #     self.setDriver('GV4', positions["tilt"], force= True)
        elif capabilities == 5:
            self.setDriver('GV2', None)
            self.setDriver('GV3', None)
            self.setDriver('GV4', t1)
        else: # 9, 10 , unknown
            self.setDriver('GV2', p1)
            self.setDriver('GV3', p2)
            self.setDriver('GV4', t1)
        return True

    def posToPercent(self, pos):
        """
        only used for PowerView G3 events
        """
        for key in pos:
            pos[key] = self.controller.toPercent(pos[key])
        return pos
        
    def cmdOpen(self, command):
        """
        open shade
        """
        LOGGER.debug('Shade Open %s', self.lpfx)
        self.positions["primary"] = 0
        self.setShadePosition(self.positions)

    def cmdClose(self, command):
        """
        close shade
        """
        LOGGER.debug('Shade Open %s', self.lpfx)
        self.positions["primary"] = 100
        self.setShadePosition(self.positions)

    def cmdStop(self, command):
        """
        stop shade
        only available in PowerView G3
        """
        if self.controller.generation == 3:
            shadeUrl = URL_SHADES_STOP.format(g=self.controller.gateway, id=self.sid)
            self.controller.put(shadeUrl)
            LOGGER.debug('Shade Stop %s', self.lpfx)

    def cmdTiltOpen(self, command):
        """
        tilt shade open
        excluded from PowerView G2
        """
        if self.controller.generation == 3:
            LOGGER.debug('Shade TiltOpen %s', self.lpfx)
            self.positions["tilt"] = 50
            self.setShadePosition(self.positions)

    def cmdTiltClose(self, command):
        """
        tilt shade close
        excluded from PowerView G2
        """
        if self.controller.generation == 3:
            LOGGER.debug('Shade TiltClose %s', self.lpfx)
            self.positions['tilt'] = 0
            self.setShadePosition(self.positions)

    def cmdJog(self, command):
        """
        jog shade
        PowerView G2 will send updateBatteryLevel which also jogs shade
        Battery level updates are automatic in PowerView G3
        """
        if self.controller.generation == 2:
            shadeUrl = URL_G2_SHADE_BATTERY.format(g=self.controller.gateway, id=self.sid)
            body = {}
        else:
            shadeUrl = URL_SHADES_MOTION.format(g=self.controller.gateway, id=self.sid)
            body = {
                "motion": "jog"
            }

        self.controller.put(shadeUrl, data=body)
        LOGGER.debug('Shade JOG %s', self.lpfx)

    def cmdCalibrate(self, command):
        """
        calibrate shade
        only available in PowerView G2, automatic in PowerView G3
        TODO not implemented
        """
        if self.controller.generation == 2:
            shadeUrl = URL_G2_SHADE.format(g=self.controller.gateway, id=self.sid)
            body = {
                'shade': {
                    "motion": 'calibrate'
                }
            }

            self.controller.put(shadeUrl, data=body)
            LOGGER.debug('Shade CALIBRATE %s', self.lpfx)
                
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
            self.setShadePosition(self.positions)
        except:
            LOGGER.error('Shade Setpos failed %s', self.lpfx)

    def setShadePosition(self, pos):
        positions_array = {}
        if self.controller.generation == 2:
            pos1 = int
            posk1 = int
            pos2 = int
            posk2 = int
            if pos.get('primary') in range(0, 101):
                pos1 = self.fromPercent(pos.get('primary', '0'), G2_DIVR)

            if pos.get('secondary') in range(0, 101):
                pos2 = self.fromPercent(pos.get('secondary', '0'), G2_DIVR)

            if 'position1' in self.shadedata['positions']:
                posk1 = self.shadedata['positions']['posKind1']
                positions_array.update({'posKind1': posk1, 'position1': pos1})

            if 'position2' in self.shadedata['positions']:
                posk2 = self.shadedata['positions']['posKind2']
                positions_array.update({'posKind2': posk2, 'position2': pos2})

            pos = {
                "shade": {
                    "positions": positions_array
                }
            }
            shade_url = URL_G2_SHADE.format(g=self.controller.gateway, id=self.sid)
        else:
            if pos.get('primary') in range(0, 101):
                positions_array["primary"] = self.fromPercent(pos.get('primary', '0'))

            if pos.get('secondary') in range(0, 101):
                positions_array["secondary"] = self.fromPercent(pos.get('secondary', '0'))

            if pos.get('tilt') in range(0, 101):
                positions_array["tilt"] = self.fromPercent(pos.get('tilt', '0'))

            if pos.get('velocity') in range(0, 101):
                positions_array["velocity"] = self.fromPercent(pos.get('velocity', '0'))

            pos = {'positions': positions_array}
            shade_url = URL_SHADES_POSITIONS.format(g=self.controller.gateway, id=self.sid)

        self.controller.put(shade_url, data=pos)
        LOGGER.debug(f"setShadePosition = {shade_url} , {pos}")
        return True

    def fromPercent(self, pos, divr=1.0):
        if self.controller.generation == 2:
            newpos = math.trunc((float(pos) / 100.0) * divr + 0.5)
        else:
            newpos = (float(pos) / 100.0) * divr
        LOGGER.debug(f"fromPercent: pos={pos}, becomes {newpos}")
        return newpos

    # all the drivers - for reference
            # TODO velocity not implemented
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

    """
    Shade Capabilities:

    Type 0 - Bottom Up 
    Examples: Standard roller/screen shades, Duette bottom up 
    Uses the “primary” control type

    Type 1 - Bottom Up w/ 90° Tilt 
    Examples: Silhouette, Pirouette 
    Uses the “primary” and “tilt” control types

    Type 2 - Bottom Up w/ 180° Tilt 
    Example: Silhouette Halo 
    Uses the “primary” and “tilt” control types

    Type 3 - Vertical (Traversing) 
    Examples: Skyline, Duette Vertiglide, Design Studio Drapery 
    Uses the “primary” control type

    Type 4 - Vertical (Traversing) w/ 180° Tilt 
    Example: Luminette 
    Uses the “primary” and “tilt” control types

    Type 5 - Tilt Only 180° 
    Examples: Palm Beach Shutters, Parkland Wood Blinds 
    Uses the “tilt” control type

    Type 6 - Top Down 
    Example: Duette Top Down 
    Uses the “primary” control type

    Type 7 - Top-Down/Bottom-Up (can open either from the bottom or from the top) 
    Examples: Duette TDBU, Vignette TDBU 
    Uses the “primary” and “secondary” control types

    Type 8 - Duolite (front and rear shades) 
    Examples: Roller Duolite, Vignette Duolite, Dual Roller
    Uses the “primary” and “secondary” control types 
    Note: In some cases the front and rear shades are
    controlled by a single motor and are on a single tube so they cannot operate independently - the
    front shade must be down before the rear shade can deploy. In other cases, they are independent with
    two motors and two tubes. Where they are dependent, the shade firmware will force the appropriate
    front shade position when the rear shade is controlled - there is no need for the control system to
    take this into account.

    Type 9 - Duolite with 90° Tilt 
    (front bottom up shade that also tilts plus a rear blackout (non-tilting) shade) 
    Example: Silhouette Duolite, Silhouette Adeux 
    Uses the “primary,” “secondary,” and “tilt” control types Note: Like with Type 8, these can be
    either dependent or independent.

    Type 10 - Duolite with 180° Tilt 
    Example: Silhouette Halo Duolite 
    Uses the “primary,” “secondary,” and “tilt” control types
    """
      