
"""
udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

Scene class
"""
# std libraries

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
        Initialize the node.

        :param polyglot: Reference to the Interface class
        :param primary: Parent address
        :param address: This nodes address
        :param name: This nodes name
        :param sid: scene id
        """
        super().__init__(polyglot, primary, address, name)

        self.poly = polyglot
        self.primary = primary
        self.controller = polyglot.getNode(self.primary)
        self.address = address
        self.name = name

        self.lpfx = f'{address}:{name}'
        self.sid = sid

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)

    def start(self):
        """
        Optional.
        This method is called after Polyglot has added the node per the
        START event subscription above
        """
        self.setDriver('ST', 0,report=True, force=True)
        LOGGER.debug(f'{self.lpfx}: get ST={self.getDriver("ST")}')
        self.setDriver('GV0', int(self.sid),report=True, force=True)
        LOGGER.debug(f'{self.lpfx}: get GV0={self.getDriver("GV0")}')
        self.rename(self.name)

    def poll(self, flag):
        if 'longPoll' in flag:
            LOGGER.debug(f"longPoll scene {self.lpfx}")
            if self.controller.generation == 2:
                self.setDriver('ST', 0,report=True, force=True)
                # manually turn off activation for G2
        else:
            # LOGGER.debug(f"shortPoll {self.lpfx}")
            self.events()

    def events(self):
       # home update event
       # Process events from the gateway.
        event = list(filter(lambda events: events['evt'] == 'home', self.controller.gateway_event))
        if event:
            event = event[0]
            if event['scenes'].count(self.sid) > 0:
                try:
                    LOGGER.info(f'shortPoll scene {self.sid} update')
                    if self.controller.generation == 2:
                        try:
                            data = list(filter(lambda scene: scene['id'] == self.sid, self.controller.scenes_array))
                        except:
                            LOGGER.error('scene: sid:{self.sid}, data error')
                            data = None
                    else:
                        data = list(filter(lambda scene: scene['_id'] == self.sid, self.controller.scenes_array))

                    if data is not None:
                        self.scenedata = data[0]
                        if self.name != self.scenedata['name']:
                            LOGGER.info(f"scene: sid:{self.sid}, name != scenedata[name]")
                            if self.controller.generation == 2:
                                LOGGER.info(f"scene: sid:{self.sid}, self.name:{self.name}, id:{self.scenedata['id']}, name:{self.scenedata['name']}")
                            else:
                                LOGGER.info(f"scene: sid:{self.sid}, self.name:{self.name}, _id:{self.scenedata['_id']}, name:{self.scenedata['name']}")
                            LOGGER.info(f"scene name changed from {self.name} to {self.scenedata['name']}")
                            self.rename(self.scenedata['name'])
                        if self.controller.generation == 3:
                            # update activation state only if G3 as array is [] for G2
                            old = self.getDriver('ST')
                            if self.controller.sceneIdsActive_array.count(self.sid) > 0:
                                if old != 1:
                                    self.setDriver('ST', 1,report=True, force=True)
                                    LOGGER.info(f"scene {self.sid} activation updated ON")
                            else:
                                if old != 0:
                                    self.setDriver('ST', 0,report=True, force=True)
                                    LOGGER.info(f"scene {self.sid} activation updated OFF")
                        
                    self.controller.gateway_event[self.controller.gateway_event.index(event)]['scenes'].remove(self.sid)
                except Exception:
                    LOGGER.error(f"scene event error sid = {self.sid}")
            else:
                pass
                # LOGGER.debug(f'shortPoll scene {self.sid} home evt but update already')
        else:
            pass
            # LOGGER.debug(f'shortPoll scene {self.sid} no home evt')

        # NOTE rest of the events below are only for G3, will not fire for G2
        event = list(filter(lambda events: (events['evt'] == 'scene-activated' or events['evt'] == 'scene-deactivated'), \
                            self.controller.gateway_event))
        if event:
            event = event[0]
            # LOGGER.debug(f"shortpoll scene {self.sid} - {event['id']} - {event}")
            if int(event['id']) == int(self.sid):
                act = event['evt'] == 'scene-activated'
                if act:
                    self.setDriver('ST', 1,report=True, force=True)
                else:
                    self.setDriver('ST', 0,report=True, force=True)
                LOGGER.info(f"shortPoll {event['evt']}: {self.lpfx}")
                self.controller.gateway_event.remove(event)
                
    def cmdActivate(self, command = None):
        """
        activate scene
        """
        if self.controller.generation == 2:
            activateSceneUrl = URL_G2_SCENES_ACTIVATE.format(g=self.controller.gateway, id=self.sid)
            self.controller.get(activateSceneUrl)
        else:
            activateSceneUrl = URL_SCENES_ACTIVATE.format(g=self.controller.gateway, id=self.sid)
            self.controller.put(activateSceneUrl)

        LOGGER.info(f"cmdActivate initiate {self.lpfx} , {command}")

        # for PowerView G2 gateway there is no event so manually trigger activate
        # PowerView G3 will receive an activate event when the motion is complete
        if self.controller.generation == 2:
            self.setDriver('ST', 1,report=True, force=True)
            # manually turn on for G2, turn off on the next longPoll

    def query(self, command = None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        self.reportDrivers()
        LOGGER.info(f'cmd Query {self.lpfx} , {command}')

    """
    This is an array of dictionary items containing the variable names(drivers)
    values and uoms(units of measure) from ISY. This is how ISY knows what kind
    of variable to display. Check the UOM's in the WSDK for a complete list.
    UOM 2 is boolean so the ISY will display 'True/False'
    """
    drivers = [
        {'driver': 'GV0', 'value': 0, 'uom': 25, 'name': "Scene Id"},
        {'driver': 'ST', 'value': 0, 'uom': 2, 'name': "Activated"},
    ]

    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
                    'ACTIVATE': cmdActivate,
                    'QUERY': query,
                }

