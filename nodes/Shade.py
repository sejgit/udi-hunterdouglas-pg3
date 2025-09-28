"""
udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

Shade class
"""

# std libraries
import math, datetime
from datetime import datetime, timezone
from threading import Thread

# external libraries
import udi_interface

LOGGER = udi_interface.LOGGER


"""
HunterDouglas PowerView G3 url's
"""
URL_DEFAULT_GATEWAY = 'powerview-g3.local'
URL_GATEWAY = 'http://{g}/gateway'
URL_HOME = 'http://{g}/home'
URL_ROOMS = 'http://{g}/home/rooms'
URL_ROOM = 'http://{g}/home/rooms/{id}'
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
from api file: [[https://github.com/sejgit/indigo-powerview/blob/master/PowerView%20API.md]]
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
    Node for shades which sets and responds to shade position & status.
    """
    def __init__(self, polyglot, primary, address, name, sid):
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
        self.sid = sid

        self.tiltCapable = [1, 2, 4, 5, 9, 10]
        self.tiltOnly90Capable = [1, 9]
 
        self.lpfx = f'{address}:{name}'
        self.event_polling_in = False
        self._event_polling_thread = None

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)

        
    def start(self):
        """
        This method is called after Polyglot has added the node per the
        START event subscription above
        """
        self.setDriver('GV0', self.sid,report=True, force=True)
        
        # wait for controller start ready
        self.controller.ready_event.wait()
        self.updateData()

        # start event polling loop    
        if not self.event_polling_in:
            self.start_event_polling()

            
    def poll(self, flag):
        """
        Wait until all start-up is ready
        Only use shortPoll, no longPoll used
        """
        if not self.controller.ready_event:
            LOGGER.error(f"Node not ready yet, exiting {self.lpfx}")
            return
        
        if 'shortPoll' in flag:
            LOGGER.debug(f'shortPoll shade {self.lpfx}')

            # start event polling loop    
            if not self.event_polling_in:
                self.start_event_polling()

                
    def start_event_polling(self):
        """
        Run routine in a separate thread to retrieve events from array loaded by sse client from gateway.
        """
        LOGGER.info(f"start: {self.lpfx}")
        if self._event_polling_thread and self._event_polling_thread.is_alive():
            return  # Already running

        self.controller.stop_sse_client_event.clear()
        self._event_polling_thread = Thread(
            target=self._poll_events,
            name=f"ShadeEventPollingThread{self.sid}",
            daemon=True
        )
        self._event_polling_thread.start()
        LOGGER.info(f"exit: {self.lpfx}")

    def _poll_events(self):
        """
        Retrieve gateway sse events from array.
        """
        self.event_polling_in = True

        while not self.controller.stop_sse_client_event.is_set():
            # wait for events to process
            gateway_events = self.controller.get_gateway_event()

            # home update event
            # Use next() with a generator expression for efficient lookup
            try:
                home_event = next((e for e in gateway_events if e.get('evt') == 'home'), None)
            except Exception as ex:
                LOGGER.error(f"shade {self.sid} home event error: {ex}", exc_info=True)
                home_event = None

            if home_event:
                try:
                    if self.sid in home_event.get('shades', []):
                        LOGGER.debug(f'shade {self.sid} update')
                        if self.updateData():
                            # Directly modify the object reference
                            home_event['shades'].remove(self.sid)
                except (KeyError, ValueError) as ex:
                    LOGGER.error(f"shade event error sid = {self.sid}: {ex}", exc_info=True)

            # process G3 events
            if self.controller.generation == 3:
                try:
                    self._poll_events_for_g3(gateway_events)
                except Exception as ex:
                    LOGGER.error(f"shade:{self.sid}, g3 event error {ex}", exc_info=True)

        self.event_polling_in = False
        LOGGER.info(f"shade:{self.sid} exiting poll events due to controller shutdown")


    def _poll_events_for_g3(self, gateway_events):
        """
        Separate the G3 ONLY events.  Mostly these are done in isoDate order.
        """
        # handle the G3 events in isoDate order
        try:
            # filter events without isoDate like home
            event_nohome = (e for e in gateway_events 
                            if e.get('isoDate') is not None)
            # get most recent isoDate
            event = min(event_nohome, key=lambda x: x['isoDate'], default={})

        except (ValueError, TypeError) as ex: # Catch specific exceptions
            LOGGER.error(f"Error filtering or finding minimum event: {ex}", exc_info=True)
            event = {}

        # only process the rest for this particular shade
        if event.get('id') == self.sid:
            
            # motion-started event
            if event.get('evt') == 'motion-started':
                LOGGER.info(f'shade {self.sid} motion-started event')
                self.updatePositions(self.posToPercent(event['targetPositions']))
                self.setDriver('ST', 1,report=True, force=True)
                self.reportCmd('DON', 2)
                self.controller.remove_gateway_event(event)

            # motion-stopped event
            if event.get('evt') == 'motion-stopped':
                LOGGER.info(f'shade {self.sid} motion-stopped event')
                self.updatePositions(self.posToPercent(event['currentPositions']))
                self.setDriver('ST', 0,report=True, force=True)
                self.reportCmd('DOF', 2)
                # add event for scene active calc
                d = datetime.now(timezone.utc).isoformat().rstrip('+00:00') + 'Z'
                e = { "evt":"scene-calc", "isoDate":d, "shadeId":self.sid }
                e['scenes'] = list(self.controller.scenes_map.keys())
                self.controller.append_gateway_event(e)
                self.controller.remove_gateway_event(event)

            # shade-online event
            if event.get('evt') == 'shade-online':
                LOGGER.info(f'shade {self.sid} shade-online event')
                self.updatePositions(self.posToPercent(event['currentPositions']))
                self.controller.remove_gateway_event(event)

            # # shade-offline event
            if event.get('evt') == 'shade-offline':
                LOGGER.error(f'shade {self.sid} shade-offline event')
                self.updatePositions(self.posToPercent(event['currentPositions']))
                self.controller.remove_gateway_event(event)

            # # battery-alert event
            if event.get('evt') == 'battery-alert':
                LOGGER.error(f'shade {self.sid} battery-event')
                # the shade/event labels the battery different Status/level
                self.controller.shades_map[self.sid]["batteryStatus"] = event['batteryLevel']
                self.setDriver('GV6', event["batterylevel"],report=True, force=True)
                self.updatePositions(self.posToPercent(event['currentPositions']))
                self.controller.remove_gateway_event(event)

        
    def updateData(self):
        """
        Updade the ISY from retrieved data. Rename node if changed on gateway.
        """
        try:
            shade = self.controller.get_shade_data(self.sid)
            self.capabilities = shade.get('capabilities')
            LOGGER.debug(f"shade {self.sid} is {shade}")
            if self.name != shade['name']:
                LOGGER.warning(f"Name error current:{self.name}  new:{shade['name']}")
                self.rename(shade['name'])
                LOGGER.warning(f"Renamed {self.name}")
            self.setDriver('ST', 0,report=True, force=True)
            self.reportCmd('DOF', 2)
            self.setDriver('GV1', shade["roomId"],report=True, force=True)
            self.setDriver('GV6', shade["batteryStatus"],report=True, force=True)
            self.setDriver('GV5', self.capabilities,report=True, force=True)
            self.updatePositions(shade['positions'])
            return True
        except Exception as ex:
            LOGGER.error(f"shade {self.sid} updateData error: {ex}", exc_info=True)
            return False

        
    # A dictionary mapping capabilities to the drivers that should be set.
    # This is a class-level variable for efficiency.
    _DRIVER_MAP = {
        7: [('GV2', 'primary'), ('GV3', 'secondary')],
        8: [('GV2', 'primary'), ('GV3', 'secondary')],
        0: [('GV2', 'primary')],
        3: [('GV2', 'primary')],
        6: [('GV3', 'secondary')],
        1: [('GV2', 'primary'), ('GV4', 'tilt')],
        2: [('GV2', 'primary'), ('GV4', 'tilt')],
        4: [('GV2', 'primary'), ('GV4', 'tilt')],
        5: [('GV4', 'tilt')],
        # The `else` case can be handled with a default lookup.
    }

    
    def updatePositions(self, positions):
        """
        Update the positions of the shade.
        """
        LOGGER.info(f"shade:{self.sid}, positions:{positions}")
        
        self.controller.update_shade_data(self.sid, {'positions': positions})
        
        positions.setdefault('primary', None)
        positions.setdefault('secondary', None)
        positions.setdefault('tilt', 0 if self.capabilities in self.tiltCapable else None)

        # Dispatch logic as above
        drivers_to_set = self._DRIVER_MAP.get(self.capabilities, [
            ('GV2', 'primary'), ('GV3', 'secondary'), ('GV4', 'tilt')
        ])

        for driver_key, position_key in drivers_to_set:
            pos_value = positions.get(position_key)
            self.setDriver(driver_key, pos_value) #, report=True, force=True)

        return True

    
    def posToPercent(self, pos):
        """
        Convert a position to a percentage.
        Only used for PowerView G3 events.
        """
        new_pos = {}
        for key, value in pos.items():
            try:
                if key == 'etaInSeconds':
                    continue
                new_pos[key] = self.controller.toPercent(value)
            except (TypeError, ValueError) as ex:
                LOGGER.error(f"Failed to convert pos[{key}]='{value}' to percent: {ex}")
                new_pos[key] = 0

        return new_pos

        
    def cmdOpen(self, command):
        """
        open shade command from ISY
        """
        LOGGER.info(f'cmd Shade Open {self.lpfx}, {command}')
        self.setShadePosition({"primary": 100})
        self.reportCmd("OPEN", 2)
        LOGGER.debug(f"Exit {self.lpfx}")        

        
    def cmdClose(self, command):
        """
        close shade command from ISY
        """
        LOGGER.info(f'cmd Shade Close {self.lpfx}, {command}')
        self.setShadePosition({"primary":0})
        self.reportCmd("CLOSE", 2)
        LOGGER.debug(f"Exit {self.lpfx}")        

        
    def cmdStop(self, command):
        """
        stop shade command from ISY
        only available in PowerView G3
        """
        if self.controller.generation == 3:
            shadeUrl = URL_SHADES_STOP.format(g=self.controller.gateway, id=self.sid)
            self.controller.put(shadeUrl)
            self.reportCmd("STOP", 2)
            LOGGER.info(f'cmd Shade Stop {self.lpfx}, {command}')
        elif self.controller.generation == 2:
            LOGGER.error(f'cmd Shade Stop error (none in gen2) {self.lpfx}, {command}')


    def cmdTiltOpen(self, command):
        """
        tilt shade open command from ISY
        """
        LOGGER.info(f'cmd Shade TiltOpen {self.lpfx}, {command}')
        #self.positions["tilt"] = 50
        self.setShadePosition(pos = {"tilt": 50})
        self.reportCmd("TILTOPEN", 2)
        LOGGER.debug(f"Exit {self.lpfx}")        

        
    def cmdTiltClose(self, command):
        """
        tilt shade close command from ISY
        """
        LOGGER.info(f'cmd Shade TiltClose {self.lpfx}, {command}')
        #self.positions['tilt'] = 0
        self.setShadePosition(pos = {"tilt": 0})
        self.reportCmd("TILTCLOSE", 2)
        LOGGER.debug(f"Exit {self.lpfx}")        

        
    def cmdJog(self, command = None):
        """
        jog shade command from ISY
        PowerView G2 will send updateBatteryLevel which also jogs shade
        Battery level updates are automatic in PowerView G3
        """
        LOGGER.info(f'cmd Shade Jog {self.lpfx}, {command}')
        if self.controller.generation == 2:
            shadeUrl = URL_G2_SHADE_BATTERY.format(g=self.controller.gateway, id=self.sid)
            body = {}
        elif self.controller.generation == 3:
            shadeUrl = URL_SHADES_MOTION.format(g=self.controller.gateway, id=self.sid)
            body = {
                "motion": "jog"
            }
        else:
            return
        self.controller.put(shadeUrl, data=body)
        self.reportCmd("JOG", 2)
        LOGGER.debug(f"Exit {self.lpfx}")        

        
    def cmdCalibrate(self, command = None):
        """
        calibrate shade from ISY
        only available in PowerView G2, automatic in PowerView G3
        """
        LOGGER.info(f'cmd Shade CALIBRATE {self.lpfx}, {command}')
        if self.controller.generation == 2:
            shadeUrl = URL_G2_SHADE.format(g=self.controller.gateway, id=self.sid)
            body = {
                'shade': {
                    "motion": 'calibrate'
                }
            }
            self.controller.put(shadeUrl, data=body)
        elif self.controller.generation == 3:
            LOGGER.error(f'cmd Shade CALIBRATE error, not implimented in G3 {self.lpfx}, {command}')            
        LOGGER.debug(f"Exit {self.lpfx}")        

        
    def query(self, command = None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        LOGGER.info(f'cmd Query {self.lpfx}, {command}')
        self.updateData()
        self.reportDrivers()
        LOGGER.debug(f"Exit {self.lpfx}")        

        
    def cmdSetpos(self, command = None):
        """
        Set the position of the shade; setting primary, secondary, tilt
        """
        LOGGER.info(f'cmdSetpos {self.lpfx}, {command}')
        if command:
            try:
                pos = {}
                query = command.get("query")
                LOGGER.debug(f'Shade Setpos query {query}')
                if "SETPRIM.uom100" in query:
                    pos["primary"] = int(query["SETPRIM.uom100"])
                if "SETSECO.uom100" in query:
                    pos["secondary"] = int(query["SETSECO.uom100"])
                if "SETTILT.uom100" in query:
                    pos["tilt"] = int(query["SETTILT.uom100"])
                if pos != {}:
                    LOGGER.info(f'Shade Setpos {pos}')
                    self.setShadePosition(pos)
                    # self.positions.update(pos)
                else:
                    LOGGER.error('Shade Setpos --nothing to set--')
            except Exception as ex:
                LOGGER.error(f'Shade Setpos failed {self.lpfx}: {ex}', exc_info=True)
        else:
            LOGGER.error("No positions given")
        LOGGER.debug(f"Exit {self.lpfx}")

        
    def _get_g2_positions(self, pos):
        """
        Helper function to build G2 positions payload.
        g2 uses posKind1/2/3 which are mapped
        """
        positions_array = {}

        if self.capabilities in self.tiltCapable and 'tilt' in pos:
            tilt = pos['tilt']
            if self.capabilities in self.tiltOnly90Capable and tilt >= 50:
                tilt = 49
            tilt_val = self.fromPercent(tilt, G2_DIVR)
            positions_array.update({'posKind1': 3, 'position1': tilt_val})

        if 'primary' in pos:
            pos1 = self.fromPercent(pos['primary'], G2_DIVR)
            positions_array.update({'posKind1': 1, 'position1': pos1})

        if 'secondary' in pos:
            pos2 = self.fromPercent(pos['secondary'], G2_DIVR)
            positions_array.update({'posKind2': 2, 'position2': pos2})

        return {"shade": {"positions": positions_array}}

    
    def _get_g3_positions(self, pos):
        """Helper function to build G3 positions payload."""
        positions_array = {}

        for key, value in pos.items():
            if key == 'tilt' and self.capabilities in self.tiltCapable:
                if self.capabilities in self.tiltOnly90Capable and value >= 50:
                    value = 49
                positions_array['tilt'] = self.fromPercent(value)
            elif key in ['primary', 'secondary', 'velocity']:
                positions_array[key] = self.fromPercent(value)

        return {'positions': positions_array}

    
    def setShadePosition(self, pos):
        """
        Sets the shade position based on the gateway generation.
        """
        if self.controller.generation == 2:
            shade_payload = self._get_g2_positions(pos)
            shade_url = URL_G2_SHADE.format(g=self.controller.gateway, id=self.sid)
        elif self.controller.generation == 3:
            shade_payload = self._get_g3_positions(pos)
            shade_url = URL_SHADES_POSITIONS.format(g=self.controller.gateway, id=self.sid)
        else:
            return False
        self.controller.put(shade_url, data=shade_payload)
        LOGGER.info(f"setShadePosition = {shade_url} , {shade_payload}")
        return True

    
    def fromPercent(self, pos, divr=1.0):
        """
        Convert a percentage to a position.
        """
        if self.controller.generation == 2:
            newpos = math.trunc((float(pos) / 100.0) * divr)
        elif self.controller.generation == 3:
            newpos = (float(pos) / 100.0) * divr
        else:
            return 0
        LOGGER.debug(f"fromPercent: pos={pos}, becomes {newpos}")
        return newpos

    
    # all the drivers - for reference
    # NOTE velocity not implemented, possible for position setting, no use in reading scenes
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
    NOTE reversed to scene labelling

    Type 8 - Duolite (front and rear shades) 
    Examples: Roller Duolite, Vignette Duolite, Dual Roller
    Uses the “primary” and “secondary” control types 
    Note: In some cases the front and rear shades are
    controlled by a single motor and are on a single tube so they cannot operate independently - the
    front shade must be down before the rear shade can deploy. In other cases, they are independent with
    two motors and two tubes. Where they are dependent, the shade firmware will force the appropriate
    front shade position when the rear shade is controlled - there is no need for the control system to
    take this into account.
    NOTE some positions are assumed in scenes, same for #9 & #10 ???

    Type 9 - Duolite with 90° Tilt 
    (front bottom up shade that also tilts plus a rear blackout (non-tilting) shade) 
    Example: Silhouette Duolite, Silhouette Adeux 
    Uses the “primary,” “secondary,” and “tilt” control types Note: Like with Type 8, these can be
    either dependent or independent.

    Type 10 - Duolite with 180° Tilt 
    Example: Silhouette Halo Duolite 
    Uses the “primary,” “secondary,” and “tilt” control types
    """
    
