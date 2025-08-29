
"""
udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

Scene class
"""
# std libraries
import time
import asyncio
from threading import Event

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
        self.event_polling_in = False

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)

        self.motionStopped_iso = []

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
        while not self.controller.ready:
            time.sleep(2)
        if not self.event_polling_in:
            self.start_event_polling()

    # TODO move after polling events
    def calcActive(self):
        # Attempt to provide scene active to G2 and speed up G3 awareness
        try:
            members = self.controller.scenes_map.get(self.sid)['members']
            LOGGER.debug(f"Members: {members}")
            match = False
            for sh in members:
                scene_shId = sh['shd_Id']                
                scene_shPos = sh['pos']
                shade = self.controller.shades_map.get(scene_shId)
                shade_pos = shade['positions']
                for element in scene_shPos.keys():
                    element2 = element
                    div = 1
                    try:
                        if element == 'vel':
                            continue
                        elif element == 'pos1':
                            if shade['capabilities'] == 7: # strange case, maybe more?
                                element2 = 'secondary'
                            else:
                                element2 = 'primary'                        
                            div = 100
                        elif element == 'pos2':
                            if shade['capabilities'] == 7: # strange case, maybe more?
                                element2 = 'primary'                        
                            else:
                                element2 = 'secondary'
                            div = 100
                        if abs(scene_shPos[element] // div - shade_pos[element2]) <= 2:
                            match = True
                        else:
                            match = False
                            break
                    except Exception as ex:
                        match = False
                        LOGGER.error(f"scene:{self.sid} shade:{scene_shId} error:{ex}", exc_info=True)
                        break
                    
                # NOTE need to fill in positions assumed for Duolite, same for 9, 10 ???
                if shade['capabilities'] == 8 and match == True:
                    #LOGGER.info(f"scene:{self.sid}, scenepos:{scene_shPos}, shade:{shade}")
                    if 'pos1' in scene_shPos:
                        if shade_pos['secondary'] != 100:
                            match = False
                    elif 'pos2' in scene_shPos:
                        if shade_pos['primary'] != 0:
                            match = False

                LOGGER.debug(f"scene:{self.sid}, scSh:{scene_shId}, scSHp:{scene_shPos}, shP:{shade_pos}, match: {match}")
                if match == False:
                    break
            if match == True:
                self.controller.sceneIdsActive_calc=list(set(self.controller.sceneIdsActive_calc+[self.sid]))
                self.controller.sceneIdsActive_calc.sort()
                LOGGER.info(f"scene:{self.sid}, sceneIdsActive_calc:{self.controller.sceneIdsActive_calc}")
                self.setDriver('GV1', 1, report=True, force=True)
                # self.reportCmd("DON",2) # TODO decide if these become the 'real' activation
            else:
                if self.sid in self.controller.sceneIdsActive_calc:
                    self.controller.sceneIdsActive_calc.remove(self.sid)
                self.setDriver('GV1', 0, report=True, force=True)
                # self.reportCmd("DOF",2)

        except Exception as ex:
            LOGGER.error(f"scene:{self.sid} FAIL error:{ex}", exc_info=True)
            self.setDriver('GV1', 0, report=True, force=True)
            # self.reportCmd("DOF",2)
                
    def poll(self, flag):
        """
        Wait until all start-up is ready
        Only use shortPoll, no longPoll used
        """
        if not self.controller.ready:
            LOGGER.error(f"Node not ready yet, exiting {self.lpfx}")
            return

        if 'shortPoll' in flag:
            LOGGER.debug(f"shortPoll scene {self.lpfx}")
            if not self.event_polling_in:
                self.start_event_polling()
            if self.controller.generation == 2:
                self.setDriver('ST', 0,report=True, force=True)
                self.reportCmd("DOF",2)
                # manually turn off activation for G2

    def start_event_polling(self):
        """
        Run routine in a thread-safe loop to retrieve events from array loaded by sse client from gateway.
        """
        future = asyncio.run_coroutine_threadsafe(self._poll_events(), self.controller.mainloop)
        LOGGER.info(f"start: {self.lpfx}")
        return future
            
    async def _poll_events(self):
        """
        Retrieve gateway sse events from array.
        """
        self.event_polling_in = True
        while not Event().is_set():
            await asyncio.sleep(1)
            # home update event
            try:
                event = list(filter(lambda events: (events['evt'] == 'home'), self.controller.gateway_event))
            except Exception as ex:
                LOGGER.error(f"scene {self.sid} home event error: {ex}", exc_info=True)
            else:
                if event:
                    event = event[0]
                    if event['scenes'].count(self.sid) > 0:
                        try:
                            LOGGER.debug(f'scene {self.sid} update')
                            self.scenedata = self.controller.scenes_map[self.sid]
                            # update name if different
                            if self.name != self.scenedata['name']:
                                LOGGER.info(f"scene: sid:{self.sid}, name != {self.scenedata['name']}")
                                if self.controller.generation == 2:
                                    LOGGER.info(f"scene: sid:{self.sid}, \
                                        self.name:{self.name}, id:{self.scenedata['id']}, \
                                        name:{self.scenedata['name']}")
                                else:
                                    LOGGER.info(f"scene: sid:{self.sid}, \
                                        self.name:{self.name}, _id:{self.scenedata['_id']}, \
                                        name:{self.scenedata['name']}")
                                LOGGER.info(f"scene name changed from {self.name} to {self.scenedata['name']}")
                                self.rename(self.scenedata['name'])
                        except Exception:
                            LOGGER.error(f"scene event error sid = {self.sid}")

                        try:
                            # update activation state only if G3, as array is [] for G2
                            if self.controller.generation == 3:
                                old = self.getDriver('ST')
                                if self.controller.sceneIdsActive.count(self.sid) > 0:
                                    if old != 1:
                                        self.setDriver('ST', 1,report=True, force=True)
                                        self.reportCmd("DON",2)
                                        LOGGER.info(f"scene {self.sid} activation updated ON")
                                else:
                                    if old != 0:
                                        self.setDriver('ST', 0,report=True, force=True)
                                        self.reportCmd("DOF",2)
                                        LOGGER.info(f"scene {self.sid} activation updated OFF")
                                        
                                # do a scene active calc
                                self.calcActive()

                            rem = self.controller.gateway_event.index(event)
                            self.controller.gateway_event[rem]['scenes'].remove(self.sid)
                        except Exception:
                            LOGGER.error(f"scene update state error sid = {self.sid}")

            ######
            # NOTE rest of the events below are only for G3, will not fire for G2
            ######
            if self.controller.gateway == 2:
                continue

            # scene-calc event
            # from shade motion-stopped event which produced scene-calc
            # run calc active if shade is within scene
            try:
                event = list(filter(lambda events: (events['evt'] == 'scene-calc'), self.controller.gateway_event))
            except Exception as ex:
                LOGGER.error(f"scene {self.sid} scene-calc event error: {ex}", exc_info=True)
            else:
                if event:
                    event = event[0]
                    if event['scenes'].count(self.sid) > 0:
                        LOGGER.debug(f'scene-calc event:{self.sid}')
                        success = False
                        members = self.controller.scenes_map.get(self.sid)['members']
                        for sh in members:
                            if sh['shd_Id'] == event['shadeId']:
                                success = True
                                break
                        if success:                        
                            LOGGER.info(f"event {event['evt']} for existing scene: {self.lpfx}")
                            self.calcActive()
                        rem = self.controller.gateway_event.index(event)
                        self.controller.gateway_event[rem]['scenes'].remove(self.sid)
                    else:
                        if event['scenes'] == []:
                            self.controller.gateway_event.remove(event)                            
                        
            # handle the rest of events in isoDate order
            try:
                # filter events without isoDate like home
                event_nohome = (e for e in self.controller.gateway_event \
                                if e.get('isoDate') is not None)
                # get most recent isoDate
                event = min(event_nohome, key=lambda x: x['isoDate'], default={})

            except (ValueError, TypeError) as ex: # Catch specific exceptions
                LOGGER.error(f"Error filtering or finding minimum event: {ex}")
                event = {}

            # only continue for this shade
            if event.get('id') != self.sid:
                continue

            # scene-activated
            if event.get('evt') == 'scene-activated':
                LOGGER.info(f"event {event['evt']}: {self.lpfx}")
                self.setDriver('ST', 1,report=True, force=True)
                self.reportCmd("DON",2)
                self.controller.gateway_event.remove(event)
                self.calcActive()
                    
            # scene-deactivated
            if event.get('evt') == 'scene-deactivated':
                LOGGER.info(f"event {event['evt']}: {self.lpfx}")
                self.setDriver('ST', 0,report=True, force=True)
                self.reportCmd("DOF",2)
                self.controller.gateway_event.remove(event)
                self.calcActive()

            # scene-add if scene already exists
            # PowerView app: scene-add can happen if user redefines scene or adds new one
            # this is action for first type, see controller for second type
            if event.get('evt') == 'scene-add':
                LOGGER.info(f"event {event['evt']} for existing scene: {self.lpfx}, updating info from gateway.")
                self.controller.updateAllFromServer()
                self.calcActive
                self.controller.gateway_event.remove(event)

        self.event_polling_in = False
        # exit events
        
    def cmdActivate(self, command = None):
        """
        activate scene
        """
        LOGGER.info(f"cmdActivate initiate {self.lpfx} , {command}")
        if self.controller.generation == 2:
            activateSceneUrl = URL_G2_SCENES_ACTIVATE.format(g=self.controller.gateway, id=self.sid)
            self.controller.get(activateSceneUrl)
        else:
            activateSceneUrl = URL_SCENES_ACTIVATE.format(g=self.controller.gateway, id=self.sid)
            self.controller.put(activateSceneUrl)


        # for PowerView G2 gateway there is no event so manually trigger activate
        # PowerView G3 will receive an activate event when the motion is complete
        if self.controller.generation == 2:
            # manually turn on for G2, turn off on the next longPoll
            self.setDriver('ST', 1,report=True, force=True)
            self.reportCmd("DON",2)
        LOGGER.debug(f"Exit {self.lpfx}")        

    def query(self, command = None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        LOGGER.info(f'cmd Query {self.lpfx} , {command}')
        self.reportDrivers()
        LOGGER.debug(f"Exit {self.lpfx}")        

    """
    This is an array of dictionary items containing the variable names(drivers)
    values and uoms(units of measure) from ISY. This is how ISY knows what kind
    of variable to display. Check the UOM's in the WSDK for a complete list.
    UOM 2 is boolean so the ISY will display 'True/False'
    """
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 2, 'name': "Activated"},
        {'driver': 'GV0', 'value': 0, 'uom': 25, 'name': "Scene Id"},
        {'driver': 'GV1', 'value': 0, 'uom': 2, 'name': "Calc Activated"},
    ]

    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
                    'ACTIVATE': cmdActivate,
                    'QUERY': query,
                }

