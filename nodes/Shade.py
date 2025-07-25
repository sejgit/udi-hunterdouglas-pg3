
"""
udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

Shade class
"""

# std libraries
import math

# external libraries
import udi_interface

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
URL_G2_SHADE = 'http://{g}/api/shades/{id}'
URL_G2_SHADE_BATTERY = 'http://{g}/api/shades/{id}?updateBatteryLevel=true'
URL_G2_SCENES = 'http://{g}/api/scenes'
URL_G2_SCENE = 'http://{g}/api/scenes?sceneid={id}'
URL_G2_SCENES_ACTIVATE = 'http://{g}/api/scenes?sceneId={id}'
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
    def __init__(self, polyglot, primary, address, name, shade):
        """
        Initialize the node.

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
        self.shadedata = shade
        self.positions = shade['positions']
        try:
            self.capabilities = int(shade['capabilities'])
        except:
            LOGGER.error(f"no capabilties defined, use default shade")
            self.capabilities = int(0)

        if self.controller.generation == 2:
            self.sid = shade['id']
        else:
            self.sid = shade['shadeId']

        self.tiltCapable = [1, 2, 4, 5, 9, 10]
        self.tiltOnly90Capable = [1, 9]
 
        self.lpfx = f'{address}:{name}'

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)
        
    def start(self):
        """
        This method is called after Polyglot has added the node per the
        START event subscription above
        """
        self.setDriver('GV0', self.sid,report=True, force=True)
        self.updateData()
        self.reportDrivers()
        self.rename(self.name)

    def poll(self, flag):
        if 'longPoll' in flag:
            LOGGER.debug(f'longPoll shade {self.lpfx}')
        else:
            # LOGGER.debug('shortPoll (shade)')
            self.events()

    def events(self):
        # home update event
        # Process events from the gateway.
        try:
            event = list(filter(lambda events: events['evt'] == 'home', self.controller.gateway_event))
        except Exception as ex:
            LOGGER.error(f"shade {self.sid} home event error: {ex}", exc_info=True)
        else:            
            if event:
                event = event[0]
                if event['shades'].count(self.sid) > 0:
                    LOGGER.info(f'shortPoll shade {self.sid} update')
                    if self.updateData():
                        try:
                            self.controller.gateway_event[self.controller.gateway_event.index(event)]['shades'].remove(self.sid)
                        except Exception as ex:
                            LOGGER.error(f"shade event error sid = {self.sid}: {ex}", exc_info=True)
                else:
                    pass
                    # LOGGER.debug(f'shortPoll shade {self.sid} home evt but update already')
            else:
                pass
                # LOGGER.debug(f'shortPoll shade {self.sid} no home evt')

        # NOTE rest of the events below are only for G3, will not fire for G2

        # motion-started event
        try:
            event = list(filter(lambda events: (events['evt'] == 'motion-started' and events['id'] == self.sid), \
                            self.controller.gateway_event))
        except Exception as ex:
            LOGGER.error(f"shade {self.sid} motion-started event error: {ex}")
        else:
            if event:
                event = event[0]
                self.positions = self.posToPercent(event['targetPositions'])
                if self.updatePositions():
                    self.setDriver('ST', 1,report=True, force=True)
                    LOGGER.info(f'shortPoll shade {self.sid} motion-started event')
                    self.controller.gateway_event.remove(event)
                   
        # motion-stopped event
        try:
            event = list(filter(lambda events: (events['evt'] == 'motion-stopped' and events['id'] == self.sid), \
                            self.controller.gateway_event))
        except Exception as ex:
            LOGGER.error(f"shade {self.sid} motion-stopped event error: {ex}")
        else:
            if event:
                event = event[0]
                self.positions = self.posToPercent(event['currentPositions'])
                if self.updatePositions():
                    self.setDriver('ST', 0,report=True, force=True)
                    LOGGER.info(f'shortPoll shade {self.sid} motion-stopped event')
                    self.controller.gateway_event.remove(event)
                   
        # shade-online event
        try:
            event = list(filter(lambda events: (events['evt'] == 'shade-online' and events['id'] == self.sid), \
                            self.controller.gateway_event))
        except Exception as ex:
            LOGGER.error(f"shade {self.sid} shade-online event error: {ex}")
        else:
            if event:
                event = event[0]
                self.positions = self.posToPercent(event['currentPositions'])
                if self.updatePositions():
                    LOGGER.info(f'shortPoll shade {self.sid} shade-online event')
                    self.controller.gateway_event.remove(event)
                   
        # shade-offline event
        try:
            event = list(filter(lambda events: (events['evt'] == 'shade-offline' and events['id'] == self.sid), \
                            self.controller.gateway_event))
        except Exception as ex:
            LOGGER.error(f"shade {self.sid} shade-offline event error: {ex}")
        else:
            if event:
                event = event[0]
                self.positions = self.posToPercent(event['currentPositions'])
                if self.updatePositions():
                    LOGGER.error(f'shortPoll shade {self.sid} shade-offline event')
                    self.controller.gateway_event.remove(event)
                   
        # battery-alert event
        try:
            event = list(filter(lambda events: (events['evt'] == 'battery-alert' and events['id'] == self.sid), \
                            self.controller.gateway_event))
        except Exception as ex:
            LOGGER.error(f"shade {self.sid} battery-event error: {ex}")
        else:
            if event:
                event = event[0]
                self.shadedata["batteryStatus"] = event['batteryLevel']
                self.setDriver('GV6', self.shadedata["batteryStatus"],report=True, force=True)
                self.positions = self.posToPercent(event['currentPositions'])
                if self.updatePositions():
                    LOGGER.error(f'shortPoll shade {self.sid} battery-event')
                    self.controller.gateway_event.remove(event)

    def updateData(self):
        if self.controller.no_update == False:
            # LOGGER.debug(self.controller.shades_array)
            data = list(filter(lambda shade: shade['id'] == self.sid, self.controller.shades_array))
            LOGGER.debug(f"shade {self.sid} is {data}")
            if data:
                self.shadedata = data[0]
                if self.name != self.shadedata['name']:
                    LOGGER.warning(f"Name error current:{self.name}  new:{self.shadedata['name']}")
                    self.rename(self.shadedata['name'])
                    LOGGER.warning(f"Renamed {self.name}")
                self.setDriver('ST', 0,report=True, force=True)
                self.setDriver('GV1', self.shadedata["roomId"],report=True, force=True)
                self.setDriver('GV6', self.shadedata["batteryStatus"],report=True, force=True)
                try:
                    self.capabilities = int(self.shadedata["capabilities"])
                except:
                    LOGGER.error(f"no capabilties defined, use default shade")
                    self.capabilities = int(0)
                self.setDriver('GV5', self.capabilities,report=True, force=True)
                self.positions = self.shadedata["positions"]
                self.updatePositions()
                return True
        else:
            return False

    def updatePositions(self):
        """
        Update the positions of the shade.
        """
        if 'primary' in self.positions:
            p1 = self.positions['primary']
        else:
            p1 = None
        if 'secondary' in self.positions:
            p2 = self.positions['secondary']
        else:
            p2 = None
        if 'tilt' in self.positions:
            t1 = self.positions['tilt']
        else:
            if self.capabilities in self.tiltCapable:
                t1 = 0
            else:
                t1 = None
        LOGGER.debug(f"updatePositions {p1} {p2} {t1}")
            
        if self.capabilities in [7, 8]:
            self.setDriver('GV2', p1,report=True, force=True)
            self.setDriver('GV3', p2,report=True, force=True)
        elif self.capabilities in [0, 3]:
            self.setDriver('GV2', p1,report=True, force=True)
        elif self.capabilities == 6:
            self.setDriver('GV3', p2,report=True, force=True)
        elif self.capabilities in [1, 2, 4]:
            self.setDriver('GV2', p1,report=True, force=True)
            self.setDriver('GV4', t1,report=True, force=True)
        elif self.capabilities == 5:
            self.setDriver('GV4', t1,report=True, force=True)
        else: # 9, 10 , unknown
            self.setDriver('GV2', p1,report=True, force=True)
            self.setDriver('GV3', p2,report=True, force=True)
            self.setDriver('GV4', t1,report=True, force=True)
        return True

    def posToPercent(self, pos):
        """
        Convert a position to a percentage.
        """
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
        LOGGER.info(f'cmd Shade Open {self.lpfx}')
        if self.controller.generation == 2:
            self.positions["primary"] = 100
        else:
            self.positions["primary"] = 0
        self.setShadePosition(self.positions)

    def cmdClose(self, command):
        """
        close shade
        """
        LOGGER.info(f'cmd Shade Close {self.lpfx}')
        if self.controller.generation == 2:
            self.positions["primary"] = 0
        else:
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
            LOGGER.info(f'cmd Shade Stop {self.lpfx}')

    def cmdTiltOpen(self, command):
        """
        tilt shade open
        """
        LOGGER.info(f'cmd Shade TiltOpen {self.lpfx}')
        
        self.positions["tilt"] = 50
        self.setShadePosition(pos = {"tilt": 50})

    def cmdTiltClose(self, command):
        """
        tilt shade close
        """
        LOGGER.info(f'cmd Shade TiltClose {self.lpfx}')
        self.positions['tilt'] = 0
        self.setShadePosition(pos = {"tilt": 0})

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
        LOGGER.info(f'cmd Shade JOG {self.lpfx}')

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
            LOGGER.debug(f'cmd Shade CALIBRATE {self.lpfx}')
                
    def query(self, command=None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        self.updateData()
        self.reportDrivers()
        LOGGER.info(f'cmd Query {self.lpfx}')

    def cmdSetpos(self, command):
        """
        Set the position of the shade.
        """
        """
        setting primary, secondary, tilt
        """
        try:
            pos = {}
            LOGGER.info(f'Shade Setpos command {command}')
            query = command.get("query")
            LOGGER.info(f'Shade Setpos query {query}')
            if "SETPRIM.uom100" in query:
                pos["primary"] = int(query["SETPRIM.uom100"])
            if "SETSECO.uom100" in query:
                pos["secondary"] = int(query["SETSECO.uom100"])
            if "SETTILT.uom100" in query:
                pos["tilt"] = int(query["SETTILT.uom100"])
            if pos != {}:
                LOGGER.info(f'Shade Setpos {pos}')
                self.setShadePosition(pos)
                self.positions.update(pos)
            else:
                LOGGER.error('Shade Setpos --nothing to set--')
        except Exception as ex:
            LOGGER.error(f'Shade Setpos failed {self.lpfx}: {ex}', exc_info=True)

    def setShadePosition(self, pos):
        positions_array = {}
        if self.controller.generation == 2:
            if self.capabilities in self.tiltCapable:
                if 'tilt' in pos:
                    tilt = pos['tilt']
                    if self.capabilities in self.tiltOnly90Capable:
                        if tilt >= 50:
                            tilt = 49
                    tilt = self.fromPercent(tilt, G2_DIVR)
                    posk1 = 3
                    positions_array.update({'posKind1': posk1, 'position1': tilt})

            if 'primary' in pos:
                pos1 = self.fromPercent(pos['primary'], G2_DIVR)
                posk1 = 1
                positions_array.update({'posKind1': posk1, 'position1': pos1})

            if 'secondary' in pos:
                pos2 = self.fromPercent(pos['secondary'], G2_DIVR)
                posk2 = 2 #unknown if this is the only possible number
                positions_array.update({'posKind2': posk2, 'position2': pos2})

            pos = {
                "shade": {
                    "positions": positions_array
                }
            }
            shade_url = URL_G2_SHADE.format(g=self.controller.gateway, id=self.sid)
        else:
            if 'primary' in pos:
                positions_array["primary"] = self.fromPercent(pos['primary'])

            if 'secondary' in pos:
                positions_array["secondary"] = self.fromPercent(pos['secondary'])

            if self.capabilities in self.tiltCapable:
                if 'tilt' in pos:
                    tilt = pos['tilt']
                    if self.capabilities in self.tiltOnly90Capable:
                        if tilt >= 50:
                            tilt = 49                    
                    positions_array["tilt"] = self.fromPercent(tilt)

            if 'velocity' in pos:
                positions_array["velocity"] = self.fromPercent(pos['velocity'])

            pos = {'positions': positions_array}
            shade_url = URL_SHADES_POSITIONS.format(g=self.controller.gateway, id=self.sid)

        self.controller.put(shade_url, data=pos)
        LOGGER.info(f"setShadePosition = {shade_url} , {pos}")
        return True

    def fromPercent(self, pos, divr=1.0):
        """
        Convert a percentage to a position.
        """
        if self.controller.generation == 2:
            newpos = math.trunc((float(pos) / 100.0) * divr)
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
        'QUERY': query,
        'SETPOS': cmdSetpos
    }

    
###################
# Shade sub-classes
###################

class ShadeNoTilt(Shade):
    id = 'shadenotiltid'

    drivers = [
        {'driver': 'GV0', 'value': 0, 'uom': 107, 'name': "Shade Id"},
        {'driver': 'ST', 'value': 0, 'uom': 2, 'name': "In Motion"}, 
        {'driver': 'GV1', 'value': 0, 'uom': 107, 'name': "Room Id"},
        {'driver': 'GV2', 'value': None, 'uom': 100, 'name': "Primary"},
        {'driver': 'GV3', 'value': None, 'uom': 100, 'name': "Secondary"},
        {'driver': 'GV5', 'value': 0, 'uom': 25, 'name': "Capabilities"},
        {'driver': 'GV6', 'value': 0, 'uom': 25, 'name': "Battery Status"},
        ]

class ShadeOnlyPrimary(Shade):
    id = 'shadeonlyprimid'

    drivers = [
        {'driver': 'GV0', 'value': 0, 'uom': 107, 'name': "Shade Id"},
        {'driver': 'ST', 'value': 0, 'uom': 2, 'name': "In Motion"}, 
        {'driver': 'GV1', 'value': 0, 'uom': 107, 'name': "Room Id"},
        {'driver': 'GV2', 'value': None, 'uom': 100, 'name': "Primary"},
        {'driver': 'GV5', 'value': 0, 'uom': 25, 'name': "Capabilities"},
        {'driver': 'GV6', 'value': 0, 'uom': 25, 'name': "Battery Status"},
        ]

class ShadeOnlySecondary(Shade):
    id = 'shadeonlysecondid'

    drivers = [
            {'driver': 'GV0', 'value': 0, 'uom': 107, 'name': "Shade Id"},
            {'driver': 'ST', 'value': 0, 'uom': 2, 'name': "In Motion"}, 
            {'driver': 'GV1', 'value': 0, 'uom': 107, 'name': "Room Id"},
            {'driver': 'GV3', 'value': None, 'uom': 100, 'name': "Secondary"},
            {'driver': 'GV5', 'value': 0, 'uom': 25, 'name': "Capabilities"},
            {'driver': 'GV6', 'value': 0, 'uom': 25, 'name': "Battery Status"},
            ]

class ShadeNoSecondary(Shade):
    id = 'shadenosecondid'

    drivers = [
        {'driver': 'GV0', 'value': 0, 'uom': 107, 'name': "Shade Id"},
        {'driver': 'ST', 'value': 0, 'uom': 2, 'name': "In Motion"}, 
        {'driver': 'GV1', 'value': 0, 'uom': 107, 'name': "Room Id"},
        {'driver': 'GV2', 'value': None, 'uom': 100, 'name': "Primary"},
        {'driver': 'GV4', 'value': None, 'uom': 100, 'name': "Tilt"},
        {'driver': 'GV5', 'value': 0, 'uom': 25, 'name': "Capabilities"},
        {'driver': 'GV6', 'value': 0, 'uom': 25, 'name': "Battery Status"},
        ]

class ShadeOnlyTilt(Shade):
    id = 'shadeonlytiltid'

    drivers = [
        {'driver': 'GV0', 'value': 0, 'uom': 107, 'name': "Shade Id"},
        {'driver': 'ST', 'value': 0, 'uom': 2, 'name': "In Motion"}, 
        {'driver': 'GV1', 'value': 0, 'uom': 107, 'name': "Room Id"},
        {'driver': 'GV4', 'value': None, 'uom': 100, 'name': "Tilt"},
        {'driver': 'GV5', 'value': 0, 'uom': 25, 'name': "Capabilities"},
        {'driver': 'GV6', 'value': 0, 'uom': 25, 'name': "Battery Status"},
        ]
    
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
    
