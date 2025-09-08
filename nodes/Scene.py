"""
udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

Scene class
"""
# std libraries
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
    Node for scenes which sets and responds to activation of scenes.
    GV0 scene Id is just for reference
    GV1 using calculation of shade position as feedback check on gateway (just for debug)
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
        self._event_polling_thread = None
        
        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)

        
    def start(self):
        """
        Optional.
        This method is called after Polyglot has added the node per the
        START event subscription above
        """
        self.rename(self.name)

        # wait for controller start ready
        self.controller.ready_event.wait()

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
            LOGGER.debug(f"shortPoll scene {self.lpfx}")
            
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
            name=f"SceneEventPollingThread{self.sid}",
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
            # Efficiently find the 'home' event using next() with a default value.
            try:
                event = next((e for e in gateway_events
                              if e.get('evt') == 'home'), None)
            except Exception as ex:
                LOGGER.error(f"scene {self.sid} home event lookup error: {ex}", exc_info=True)
                event = None

            if event:
                try:
                    if self.sid in event.get('scenes', []):
                        LOGGER.debug(f'scene {self.sid} update')

                        # Update scene data
                        self.scenedata = self.controller.scenes_map[self.sid]

                        # Check and update name if different
                        if self.name != self.scenedata.get('name'):
                            LOGGER.info(f"scene name for sid:{self.sid}"
                                        f" changed from {self.name} to {self.scenedata.get('name')}")
                            self.rename(self.scenedata.get('name'))

                        # Remove sid from the scenes list in the home event
                        event['scenes'].remove(self.sid)

                        # calcActive call is where active and check is updated to isy
                        try:
                            self.calcActive()
                        except Exception as ex:
                            LOGGER.error(f"self.calcActive error for sid={self.sid}: {ex}", exc_info=True)

                except (KeyError, ValueError) as ex:
                    LOGGER.error(f"scene event error sid = {self.sid}: {ex}", exc_info=True)

            # process G3 events
            if self.controller.generation == 3:
                try:
                    self._poll_events_for_g3(gateway_events)
                except Exception as ex:
                    LOGGER.error(f"scene:{self.sid}, g3 event error {ex}", exc_info=True)

        self.event_polling_in = False
        LOGGER.info(f"shade:{self.sid} exiting poll events due to controller shutdown")


    def _poll_events_for_g3(self, gateway_events):
        """
        Separate the G3 ONLY events.  Mostly these are done in isoDate order.
        """
        # scene-calc event
        # from shade motion-stopped event which produced scene-calc
        # run calc active if shade is within scene
        try:
            event = next((e for e in gateway_events
                                     if e.get('evt') == 'scene-calc'), None)
        except Exception as ex:
            LOGGER.error(f"scene {self.sid} scene-calc event lookup error: {ex}", exc_info=True)
            event = None

        if event:
            try:
                members = self.controller.scenes_map.get(self.sid, {}).get('members', [])

                if any(sh['shd_Id'] == event['shadeId'] for sh in members):
                    LOGGER.debug(f'scene-calc event:{self.sid}')
                    LOGGER.info(f"event {event['evt']} for existing scene: {self.lpfx}")
                    self.calcActive()

                # Remove sid from the scenes list in the event
                # Use a guard clause to handle potential issues
                scenes_list = event.get('scenes', [])
                if self.sid in scenes_list:
                    scenes_list.remove(self.sid)

                # Clean up the event if the list of scenes is empty
                if not scenes_list:
                    self.controller.remove_gateway_event(event)

            except (KeyError, ValueError) as ex:
                LOGGER.error(f"scene-calc event error for sid {self.sid}: {ex}", exc_info=True)

        # handle the rest of events in isoDate order
        try:
            # filter events without isoDate like home
            event_nohome = (e for e in gateway_events
                            if e.get('isoDate') is not None)
            # get most recent isoDate
            event = min(event_nohome, key=lambda x: x['isoDate'], default={})

        except (ValueError, TypeError) as ex: # Catch specific exceptions
            LOGGER.error(f"Error filtering or finding minimum event: {ex}")
            event = {}

        # only process events for this shade
        if event.get('id') == self.sid:

            # scene-activated
            if event.get('evt') == 'scene-activated':
                LOGGER.info(f"event {event.get('evt')}: {self.lpfx}")
                self.controller.remove_gateway_event(event)
                self.controller.sceneIdsActive.append(self.sid)
                self.calcActive()

            # scene-deactivated
            if event.get('evt') == 'scene-deactivated':
                LOGGER.info(f"event {event.get('evt')}: {self.lpfx}")
                self.controller.remove_gateway_event(event)
                self.controller.sceneIdsActive.remove(self.sid)
                self.calcActive()

            # scene-add if scene already exists
            # PowerView app: scene-add can happen if user redefines scene or adds new one
            # this is action for first type, see controller for second type
            if event.get('evt') == 'scene-add':
                LOGGER.info(f"event {event.get('evt')} for existing scene: {self.lpfx}, updating info from gateway.")
                self.controller.updateAllFromServer()
                self.calcActive()
                self.controller.remove_gateway_event(event)
        
        
    def calcActive(self):
        """
        Uses the positions set in scene members (shades) & compared to those same shades' actual positions. 
        """
        try:
            # below should work for gen2 as well
            members = self.controller.scenes_map.get(self.sid, {}).get('members', [])
            if not members:
                self._handle_no_match()
            else:
                is_match = self._check_member_positions(members)

                if is_match:
                    self._handle_match()
                else:
                    self._handle_no_match()

        except Exception as ex:
            LOGGER.error(f"scene:{self.sid} FAIL error:{ex}", exc_info=True)
            self._handle_no_match()
            
        self.check_if_calc_active_match_gateway()
        return

    
    def _check_member_positions(self, members: list) -> bool:
        for sh in members:
            shade_id = sh.get('shd_Id')
            scene_pos = sh.get('pos', {})
            shade = self.controller.get_shade_data(shade_id)

            if not shade:
                LOGGER.warning(f"Scene {self.sid} member {shade_id} not found in shades_map.")
                return False

            shade_pos = shade.get('positions', {})

            if not self._check_individual_positions(scene_pos, shade_pos, shade):
                return False

            # Additional Duolite check
            if shade.get('capabilities') in [8, 9, 10]:
                if 'pos1' in scene_pos and shade_pos.get('secondary') != 100:
                    return False
                if 'pos2' in scene_pos and shade_pos.get('primary') != 0:
                    return False

        return True # All members matched
    

    def _check_individual_positions(self, scene_pos, shade_pos, shade) -> bool:
        for element, scene_value in scene_pos.items():
            if element in ['vel', 'etaInSeconds']:
                continue

            shade_pos_key, div = self._get_shade_position_and_div(element, shade)
            if shade_pos_key is None or div is None:
                continue

            try:
                shade_value = shade_pos.get(shade_pos_key)
                if shade_value is None:
                    LOGGER.warning(f"Position '{shade_pos_key}' not found for shade.")
                    return False

                if shade_pos_key == 'tilt':
                    LOGGER.debug(f'shade_pos_key:{shade_pos_key} scene_value:{scene_value}, shade_value:{shade_value}')
                
                if abs(scene_value // div - shade_value) > 2:
                    return False
            except (TypeError, KeyError) as ex:
                LOGGER.error(f"scene:{self.sid} shade:{shade.get('shd_Id')} position error: {ex}", exc_info=True)
                return False

        return True
    

    def _get_shade_position_and_div(self, scene_pos_key, shade):
        """
        Helper function to determine the correct shade position key and divisor.
        """
        if scene_pos_key == 'vel':
            return None, None
        elif scene_pos_key == 'pos1':
            pos_key = 'secondary' if shade.get('capabilities') == 7 else 'primary'
            return pos_key, 100
        elif scene_pos_key == 'pos2':
            pos_key = 'primary' if shade.get('capabilities') == 7 else 'secondary'
            return pos_key, 100
        elif scene_pos_key == 'tilt':
            return scene_pos_key, 1
        return None, None
    
    
    def _handle_match(self):
        """Actions to perform when a scene match is found."""
        self.controller.sceneIdsActive_calc.add(self.sid)
        LOGGER.info(f"MATCH scene:{self.sid}, sceneIdsActive_calc:{sorted(self.controller.sceneIdsActive_calc)}")
        self.setDriver('ST', 1, report=True, force=True)
        self.reportCmd("DON", 2)

        
    def _handle_no_match(self):
        """Actions to perform when no scene match is found or an error occurs."""
        self.controller.sceneIdsActive_calc.discard(self.sid)
        self.setDriver('ST', 0, report=True, force=True)
        self.reportCmd("DOF", 2)
        LOGGER.debug(f"NOMATCH scene:{self.sid}, sceneIdsActive_calc:{sorted(self.controller.sceneIdsActive_calc)}")

        
    def check_if_calc_active_match_gateway(self):
        """
        Looking to see if calculated Active scene matches the gateway data.
        """
        if self.controller.gateway == 2:
            LOGGER.info(f"check = GEN2, no action")
            do_they_agree = False
        else:        
            is_in_set = self.sid in self.controller.sceneIdsActive_calc
            is_in_list = self.sid in self.controller.sceneIdsActive

            # The collections agree if they both contain the element or both do not.
            do_they_agree = is_in_set == is_in_list

            if not do_they_agree:
                LOGGER.warning(f"scene:{self.sid} calc != gateway")
            
        return do_they_agree

    
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
        # send activate command for both gen2 and gen3
        # the DON command will come with the scene event
        self.reportCmd("ACTIVATE", 2)
        LOGGER.debug(f"Exit {self.lpfx}")        

        
    def query(self, command = None):
        """
        Called by ISY to report all drivers for this node. This is done in
        the parent class, so you don't need to override this method unless
        there is a need.
        """
        LOGGER.info(f'cmd Query {self.lpfx} , {command}')
        self.calcActive()
        self.reportDrivers()
        LOGGER.info(f'scene:{self.controller.scenes_map.get(self.sid)}')
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
        # {'driver': 'GV1', 'value': 0, 'uom': 2, 'name': "Calc agrees"},
    ]

    
    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
                    'ACTIVATE': cmdActivate,
                    'QUERY': query,
                }

