"""Module for the Hunter Douglas PowerView Scene node in a Polyglot v3 NodeServer.

This module defines the Scene class, which represents a Hunter Douglas PowerView
scene. It allows for activation of scenes and monitors their active state based
on shade positions and gateway events.

(C) 2025 Stephen Jenkins
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


class Scene(udi_interface.Node):
    """Polyglot v3 NodeServer node for Hunter Douglas PowerView Scenes.

    This class represents a Hunter Douglas PowerView scene. It allows for
    activation of scenes and monitors their active state based on shade
    positions and gateway events.

    Attributes:
        id (str): The Polyglot node ID for scenes.
    """
    id = 'sceneid'

    def __init__(self, poly, primary, address, name, sid):
        """Initializes the Scene node.

        Args:
            poly: The Polyglot interface object.
            primary: The address of the primary controller node.
            address: The address of this scene node.
            name: The name of this scene node.
            sid (str): The unique ID of the Hunter Douglas PowerView scene.
        """
        super().__init__(poly, primary, address, name)

        self.poly = poly
        self.primary = primary
        self.controller = poly.getNode(self.primary)
        self.address = address
        self.name = name
        self.sid = sid

        self.lpfx = f'{address}:{name}'
        self.event_polling_in = False
        self._event_polling_thread = None
        
        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.POLL, self.poll)

        
    def start(self):
        """Handles the startup sequence for the scene node.

        This method is called after Polyglot has added the node. It sets
        the scene ID driver and waits for the controller node to be ready
        before starting the event polling loop.
        """
        self.setDriver('GV0', self.sid)

        # wait for controller start ready
        self.controller.ready_event.wait()

        # start event polling loop    
        if not self.event_polling_in:
            self.start_event_polling()

            
    def poll(self, flag):
        """Handles polling requests from Polyglot.

        This method is called by Polyglot for polling. It ensures the
        controller is ready and starts the event polling loop if not already running.
        Currently only shortPolls are used.

        Args:
            flag (str): A string indicating the type of poll ('shortPoll').
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
        """Starts the background thread for polling and processing gateway events.

        This ensures that the event processing loop is running in its own thread,
        consuming events that are queued by the SSE client.
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
        """The main loop for processing events from the gateway event queue.

        This method runs in a dedicated thread and continuously processes events
        relevant to this scene, such as 'home' updates and Gen 3 specific events.
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
        """Processes Gen 3 specific gateway events for the scene.

        This method handles events like 'scene-calc', 'scene-activated',
        'scene-deactivated', and 'scene-add' that are specific to Gen 3
        gateways.

        Args:
            gateway_events (list[dict]): A list of gateway events to process.
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
        """Calculates if the scene is currently active based on shade positions.

        This method compares the target positions of shades within the scene
        to their actual current positions to determine if the scene is active.
        It then updates the scene's status driver accordingly.
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
        """Checks if all members of the scene are in their target positions.

        Args:
            members (list): A list of scene members, each containing shade ID
                            and target positions.

        Returns:
            bool: True if all members are in their target positions, False otherwise.
        """
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
        """Compares the target and actual positions for an individual shade.

        Args:
            scene_pos (dict): The target positions for the shade within the scene.
            shade_pos (dict): The actual current positions of the shade.
            shade (dict): The shade's full data dictionary.

        Returns:
            bool: True if the shade's actual positions match the scene's target
                  positions within an acceptable tolerance, False otherwise.
        """
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
        """Determines the correct shade position key and divisor for conversion.

        Args:
            scene_pos_key (str): The key from the scene's position data (e.g., 'pos1', 'tilt').
            shade (dict): The shade's full data dictionary.

        Returns:
            tuple: A tuple containing the shade position key (str) and the
                   divisor (int or float), or (None, None) if not applicable.
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
        """Performs actions when the scene is determined to be active.

        This includes adding the scene to the calculated active scenes set,
        setting the 'ST' driver to 1 (on), and reporting a 'DON' command.
        """
        self.controller.sceneIdsActive_calc.add(self.sid)
        LOGGER.info(f"MATCH scene:{self.sid}, sceneIdsActive_calc:{sorted(self.controller.sceneIdsActive_calc)}")
        self.setDriver('ST', 1, report=True, force=True)
        self.reportCmd("DON", 2)

        
    def _handle_no_match(self):
        """Performs actions when the scene is determined to be inactive or an error occurs.

        This includes removing the scene from the calculated active scenes set,
        setting the 'ST' driver to 0 (off), and reporting a 'DOF' command.
        """
        self.controller.sceneIdsActive_calc.discard(self.sid)
        self.setDriver('ST', 0, report=True, force=True)
        self.reportCmd("DOF", 2)
        LOGGER.debug(f"NOMATCH scene:{self.sid}, sceneIdsActive_calc:{sorted(self.controller.sceneIdsActive_calc)}")

        
    def check_if_calc_active_match_gateway(self):
        """Compares the calculated active state with the gateway's reported active state.

        This method is primarily for Gen 3 gateways to verify consistency
        between the NodeServer's internal calculation and the gateway's
        understanding of scene activity.

        Returns:
            bool: True if the calculated active state matches the gateway's
                  reported state, False otherwise.
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
        """Activates the scene on the Hunter Douglas PowerView gateway.

        This method sends the appropriate command to either a Gen 2 or Gen 3
        gateway to activate the scene. For Gen 2, it manually updates the
        driver status as no event is received.

        Args:
            command (dict, optional): The command payload from Polyglot.
                                      Defaults to None.
        """
        LOGGER.info(f"cmdActivate initiate {self.lpfx} , {command}")
        if self.controller.generation == 2:
            activateSceneUrl = URL_G2_SCENES_ACTIVATE.format(g=self.controller.gateway, id=self.sid)
            self.controller.get(activateSceneUrl)
        elif self.controller.generation == 3:
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
        """Queries the node and reports all drivers to the ISY.

        This method recalculates the scene's active state and then reports
        all driver values to the ISY.

        Args:
            command (dict, optional): The command payload from Polyglot.
                                      Defaults to None.
        """
        LOGGER.info(f'cmd Query {self.lpfx} , {command}')
        self.calcActive()
        self.reportDrivers()
        LOGGER.info(f'scene:{self.controller.scenes_map.get(self.sid)}')
        LOGGER.debug(f"Exit {self.lpfx}")        

        
    # UOMs:
    # 2: boolean
    # 25: index
    #
    # Driver controls:
    # ST: Status (Activated)
    # GV0: Custom Control 0 (Scene Id)
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 2, 'name': "Activated"},
        {'driver': 'GV0', 'value': 0, 'uom': 25, 'name': "Scene Id"},
    ]

    
    """
    This is a dictionary of commands. If ISY sends a command to the NodeServer,
    this tells it which method to call. DON calls setOn, etc.
    """
    commands = {
                    'ACTIVATE': cmdActivate,
                    'QUERY': query,
                }

