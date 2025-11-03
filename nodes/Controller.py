"""Module for the Hunter Douglas PowerView Controller node in a Polyglot v3 NodeServer.

This module defines the Controller class, which is the primary node for interacting
with the Hunter Douglas PowerView Hub (Gen 2 and Gen 3). It handles discovery of
shades and scenes, manages the connection to the gateway, polls for updates, and
processes events.

(C) 2025 Stephen Jenkins
"""


# std libraries
import asyncio, base64, json, logging, math, socket, time
from threading import Thread, Event, Lock, Condition

# external libraries
from udi_interface import Node, LOGGER, Custom, LOG_HANDLER
import requests
import aiohttp

# personal libraries
from utils.time import check_timedelta_iso

# Nodes
from nodes import *

# limit the room label length as room - shade/scene must be < 30
ROOM_NAME_LIMIT = 15


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
URL_SCENES_ACTIVE = 'http://{g}/home/scenes/active'
URL_EVENTS = 'http://{g}/home/events?sse=false&raw=true'
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

# We need an event loop as we run in a
# thread which doesn't have a loop
mainloop = asyncio.get_event_loop()


class Controller(Node):
    """Polyglot v3 NodeServer node for Hunter Douglas PowerView Gateways.

    This class represents the main controller node that communicates with the
    Hunter Douglas PowerView gateway. It is responsible for discovering and
    managing shade and scene nodes, handling user configuration, processing
    events from the gateway, and reporting status to the ISY.
    """
    id = 'hdctrl'

    def __init__(self, poly, primary, address, name):
        """Initializes the Controller node.

        Args:
            poly: An instance of the Polyglot interface.
            primary: The address of the primary node.
            address: The address of this node.
            name: The name of this node.
        """
        super(Controller, self).__init__(poly, primary, address, name)
        # importand flags, timers, vars
        self.poly = poly
        self.address = address
        self.name = name
        self.hb = 0 # heartbeat
        self.update_last = 0.0
        self.update_minimum = 3.0 # do not allow updates more often than this
        self.gateway = URL_DEFAULT_GATEWAY
        self.generation = 99 # start with unknown, 2 or 3 are only other valid
        self.eventTimer = 0
        self.numNodes = 0

        # in function vars
        self.update_in = False
        self.discovery_in = False
        self.poll_in = False
        self.sse_client_in = False
        self.event_polling_in = False
        
        # storage arrays & conditions
        self.n_queue = []
        self.queue_condition = Condition()
        self.gateways = []
        self.gateway_event = []
        self.gateway_event_condition = Condition()
        self._event_polling_thread = None

        self.rooms_map = {}
        self.shades_map = {}
        self.shades_map_lock = Lock()
        
        self.scenes_map = {}
        self.sceneIdsActive = []
        self.sceneIdsActive_calc = set()
        self.tiltCapable = [1, 2, 4, 5, 9, 10] # shade types
        self.tiltOnly90Capable = [1, 9]

        # Events
        self.ready_event = Event()
        self.stop_sse_client_event = Event()
        self.all_handlers_st_event = Event()
        
        # Create data storage classes
        self.Notices         = Custom(self.poly, 'notices')
        self.Parameters      = Custom(self.poly, 'customparams')
        self.Data            = Custom(self.poly, 'customdata')
        self.TypedParameters = Custom(self.poly, 'customtypedparams')
        self.TypedData       = Custom(self.poly, 'customtypeddata')

        # startup completion flags
        self.handler_params_st = False
        self.handler_data_st = False
        self.handler_typedparams_st = False
        self.handler_typeddata_st = False

        # Subscribe to various events from the Interface class.
        # The START event is unique in that you can subscribe to 
        # the start event for each node you define.

        self.poly.subscribe(self.poly.START,             self.start, address)
        self.poly.subscribe(self.poly.POLL,              self.poll)
        self.poly.subscribe(self.poly.LOGLEVEL,          self.handleLevelChange)
        self.poly.subscribe(self.poly.CONFIGDONE,        self.config_done)
        self.poly.subscribe(self.poly.CUSTOMPARAMS,      self.parameterHandler)
        self.poly.subscribe(self.poly.CUSTOMDATA,        self.dataHandler)
        self.poly.subscribe(self.poly.STOP,              self.stop)
        self.poly.subscribe(self.poly.DISCOVER,          self.discover_cmd)
        self.poly.subscribe(self.poly.CUSTOMTYPEDDATA,   self.typedDataHandler)
        self.poly.subscribe(self.poly.CUSTOMTYPEDPARAMS, self.typedParameterHandler)
        self.poly.subscribe(self.poly.ADDNODEDONE,       self.node_queue)

        # Tell the interface we have subscribed to all the events we need.
        # Once we call ready(), the interface will start publishing data.
        self.poly.ready()

        # Tell the interface we exist.  
        self.poly.addNode(self, conn_status='ST')

        
    def start(self):
        """Handles the startup sequence for the node.

        This method is called once by Polyglot at startup. It initializes
        the controller, sets up custom parameters, establishes a connection
        to the gateway, performs initial discovery, and starts background
        tasks for event polling.
        """
        LOGGER.info(f"Started HunterDouglas PG3 NodeServer {self.poly.serverdata['version']}")
        self.Notices.clear()
        self.Notices['hello'] = 'Plugin Start-up'
        self.setDriver('ST', 1, report = True, force = True)
        self.update_last = 0.0
        
        # Send the profile files to the ISY if neccessary or version changed.
        self.poly.updateProfile()

        # Send the default custom parameters documentation file to Polyglot
        self.poly.setCustomParamsDoc()

        # Initializing heartbeat
        self.heartbeat()

        # set-up async loop
        self.mainloop = mainloop
        asyncio.set_event_loop(mainloop)
        self.connect_thread = Thread(target=mainloop.run_forever)
        self.connect_thread.start()

        # Wait for all handlers to finish
        LOGGER.warning(f'Waiting for all handlers to complete...')
        self.all_handlers_st_event.wait(timeout=300)
        if not self.all_handlers_st_event.is_set():
            # start-up failed
            LOGGER.error("Timed out waiting for handlers to startup")
            self.setDriver('ST', 2) # start-up failed
            self.Notices['error'] = 'Error start-up timeout.  Check config / hardware & restart'
            return

        # Discover and wait for discovery to complete
        discoverSuccess = asyncio.run_coroutine_threadsafe(self.discover(), self.mainloop).result()

        # first update from Gateway
        if not discoverSuccess:
            # start-up failed
            LOGGER.error(f'First discovery & update from Gateway failed!!! exit {self.name}')
            self.Notices['error'] = 'Error first discovery-update.  Check config / hardware & restart'
            self.setDriver('ST', 2)
            return

        # fist update of shade & scene nodes
        with self.shades_map_lock:
            self.gateway_event.append({
                'evt': 'home',
                'shades': list(self.shades_map.keys()),
                'scenes': list(self.scenes_map.keys())
            })
        LOGGER.info(f"first update event[0]: {self.gateway_event[0]}")

        # first start of sse client via the async loop
        if not self.sse_client_in:
            self.start_sse_client()

        # start event polling loop    
        if not self.event_polling_in:
            self.start_event_polling()

        # signal to the nodes, its ok to start
        self.ready_event.set()

        # clear inital start-up message
        if self.Notices.get('hello'):
            self.Notices.delete('hello')

        LOGGER.info(f'exit {self.name}')


    def node_queue(self, data):
        """Queues a node address to signify its creation is complete.

        This method, used in conjunction with wait_for_node_done(), provides a
        mechanism to synchronize node creation, as the addNode operation is
        asynchronous.

        Args:
            data (dict): The data payload from the ADDNODEDONE event,
                         containing the node's address.
        """
        address = data.get('address')
        if address:
            with self.queue_condition:
                self.n_queue.append(address)
                self.queue_condition.notify()


    def wait_for_node_done(self):
        """Waits for a node to be fully added before proceeding.

        See node_queue() for more details on the synchronization mechanism.
        """
        with self.queue_condition:
            while not self.n_queue:
                self.queue_condition.wait(timeout = 0.2)
            self.n_queue.pop()


    def get_shade_data(self, sid):
        """Gets shade data from the internal map in a thread-safe manner.

        Args:
            sid (int): The ID of the shade to retrieve.

        Returns:
            dict or None: The shade data dictionary if found, otherwise None.
        """
        with self.shades_map_lock:
            return self.shades_map.get(sid)
        
    def update_shade_data(self, sid, data):
        """Updates or adds shade data in the internal map in a thread-safe manner.

        Args:
            sid (int): The ID of the shade to update or add.
            data (dict): The dictionary of shade data to store.
        """
        with self.shades_map_lock:
            if sid in self.shades_map:
                self.shades_map[sid].update(data)
            else:
                self.shades_map[sid] = data


    def append_gateway_event(self, event):
        """Appends a new event from the gateway to the event queue.

        This method is called by the SSE client thread to add an incoming event
        to the shared gateway_event list and notify consumer threads that a new
        event is available.

        Args:
            event (dict): The event data received from the gateway.
        """
        with self.gateway_event_condition:
            self.gateway_event.append(event)
            self.gateway_event_condition.notify_all()  # Wake up all waiting consumers


    def get_gateway_event(self) -> list[dict]:
        """Waits for and returns the list of gateway events.

        This method is used by consumer threads to wait for new events to be
        posted to the gateway_event list. It blocks until events are available.

        Returns:
            list[dict]: A reference to the list containing gateway events.
        """
        with self.gateway_event_condition:
            while not self.gateway_event:
                self.gateway_event_condition.wait()
            return self.gateway_event  # return reference, not a copy


    def remove_gateway_event(self, event):
        """Removes a processed event from the gateway event queue.

        Args:
            event (dict): The event object to remove from the queue.
        """
        with self.gateway_event_condition:
            if event in self.gateway_event:
                self.gateway_event.remove(event)

                
    def config_done(self):
        """Finalizes configuration setup after Polyglot has loaded.

        This method is called by Polyglot once the configuration is fully loaded.
        It's used to set up features that depend on the initial configuration,
        such as custom log levels.
        """
        LOGGER.debug(f'enter')
        self.poly.addLogLevel('DEBUG_MODULES',9,'Debug + Modules')
        LOGGER.debug(f'exit')

        
    def dataHandler(self,data):
        """Handles the loading of custom data from Polyglot.

        This method is called on startup to load any persistent custom data
        that was saved by the node.

        Args:
            data (dict): A dictionary containing the custom data.
        """
        LOGGER.debug(f'enter: Loading data {data}')
        if data is None:
            LOGGER.warning("No custom data")
        else:
            self.Data.load(data)
            LOGGER.info(f"Custom data:{self.Data}")
        self.handler_data_st = True
        self.check_handlers()

        
    def parameterHandler(self, params):
        """Handles updates to custom parameters from the Polyglot dashboard.

        This method is called when a user changes the custom parameters in the
        Polyglot UI. It loads the new parameters and re-validates them.

        Args:
            params (dict): A dictionary of the custom parameters.
        """
        LOGGER.debug('Loading parameters now')
        if params:
            self.Parameters.load(params)
        
        defaults = {"gatewayip": "powerview-g3.local"}
        for param, default_value in defaults.items():
            if param not in self.Parameters:
                self.Parameters[param] = default_value
            if self.checkParams():
                self.handler_params_st = True
        self.check_handlers()

        
    def typedParameterHandler(self, params):
        """Handles the creation of custom typed parameters.

        This method is called when the custom typed parameters are first
        created by Polyglot.

        Args:
            params (dict): A dictionary of the typed parameters' structure.
        """
        LOGGER.debug('Loading typed parameters now')
        self.TypedParameters.load(params)
        LOGGER.debug(params)
        self.handler_typedparams_st = True
        self.check_handlers()

        
    def typedDataHandler(self, data):
        """Handles updates to custom typed data from the Polyglot dashboard.

        This method is called when a user enters or updates data in the
        custom typed parameters UI.

        Args:
            data (dict): A dictionary of the custom typed data.
        """
        LOGGER.debug(f'Loading typed data now')
        if data is None:
            LOGGER.warning("No custom data")
        else:
            self.TypedData.load(data)
        LOGGER.debug(f'Loaded typed data {data}')
        self.handler_typeddata_st = True
        self.check_handlers()

        
    def check_handlers(self):
        """Checks if all startup handlers have completed and signals an event.

        This method is called after each handler completes. Once all handlers
        (parameters, data, etc.) have finished their startup tasks, it sets
        an event to signal that the main startup process can continue.
        """
        if (self.handler_params_st and self.handler_data_st and
                    self.handler_typedparams_st and self.handler_typeddata_st):
            self.all_handlers_st_event.set()
            LOGGER.info("All parameters loaded & good")
                
                
    def handleLevelChange(self, level):
        """Handles a change in the log level.

        Args:
            level (dict): A dictionary containing the new log level.
        """
        LOGGER.info(f'enter: level={level}')
        if level['level'] < 10:
            LOGGER.info("Setting basic config to DEBUG...")
            LOG_HANDLER.set_basic_config(True,logging.DEBUG)
        else:
            LOGGER.info("Setting basic config to INFO...")
            LOG_HANDLER.set_basic_config(True,logging.INFO)
        LOGGER.info(f'exit: level={level}')

        
    def checkParams(self):
        """Validates the custom parameters for the controller.

        This method checks the 'gatewayip' parameter, resolves the gateway
        address(es), and determines the gateway generation (Gen 2 or Gen 3).

        Returns:
            bool: True if parameters are valid, False otherwise.
        """
        self.Notices.delete('gateway')
        # gatewaycheck = self.gateway
        self.gateway = self.Parameters.gatewayip

        # gatewayip is None ; assign default
        if self.gateway is None:
            self.gateway = URL_DEFAULT_GATEWAY
            LOGGER.info('Gateway not defined in customParams, using {}'.format(URL_DEFAULT_GATEWAY))
            self.Notices['gateway'] = 'No gateway defined, assume G3 default; no check; best define ip address(es)'
            return True

        # gatewayip is list or string
        try:
            if type(eval(self.gateway)) == list:
                self.gateways = eval(self.gateway)
                self.gateway = self.gateways[0]
        except:
            if type(self.gateway) == str:
                if self.gateway not in self.gateways:
                    self.gateways.append(self.gateway)
            else:
                LOGGER.error('we have a bad gateway %s', self.gateway)
                self.Notices['gateway'] = 'Please note bad gateway address check gatewayip in customParams'
                return False

        # check if valid ip address(es)
        if not self._goodip():
            return False
        LOGGER.info(f'good IPs:{self.gateways}')

        # set self.generation during G2 or G3 check
        if self._g2_or_g3():
            return True
        else:
            return False


    def _goodip(self) -> bool:
        """Validates a list of gateway IP addresses.

        It iterates through the provided IP addresses, keeping only the ones
        with a valid format.

        Returns:
            bool: True if at least one valid IP address is found, False otherwise.
        """
        good_ips = []
        for ip in self.gateways:
            try:
                socket.inet_aton(ip)
                good_ips.append(ip)
            except OSError:  # OSError is the modern base for socket.error
                LOGGER.error("Bad gateway IP address: %s", ip)

        if good_ips:
            self.Notices.delete('gateway')
            self.gateways = good_ips
            return True

        self.Notices['gateway'] = "All Gateway IPs unreachable. Check 'gatewayip' in customParams"
        return False


    def _g2_or_g3(self):
        """Determines if the configured gateways are Gen 2 or Gen 3.

        It checks the list of gateways to find a responsive primary gateway and
        sets the `self.generation` attribute accordingly.

        Returns:
            bool: True if a supported gateway is found, False otherwise.
        """
        if (self._set_gateway(3, self._is_g3_primary) or
            self._set_gateway(2, self._is_g2)):
            LOGGER.info(f'good!! gateway:{self.gateway}, gateways:{self.gateways}')
            self.Notices.delete('gateway')
            self.Notices.delete('notPrimary')
            return True

        LOGGER.info(f"No gateway found in {self.gateways}")
        self.Notices['gateway'] = 'Please note no primary gateway found in gatewayip'
        return False

        
    def _set_gateway(self, generation, check_func):
        """Helper function to find and set the active gateway.

        It iterates through the list of potential gateway IPs and uses the
        provided checking function to identify a valid gateway.

        Args:
            generation (int): The gateway generation (2 or 3) to set if found.
            check_func (callable): A function that takes an IP address and returns
                                 True if it's a valid gateway of the target type.

        Returns:
            bool: True if a gateway was successfully found and set, False otherwise.
        """
        for ip in self.gateways:
            if check_func(ip):
                self.gateway = ip
                self.generation = generation
                return True
        return False

    
    def _is_g3_primary(self, ip):
        """Checks if the given IP address is a Gen 3 primary gateway.

        Args:
            ip (str): The IP address to check.

        Returns:
            bool: True if the IP belongs to a Gen 3 primary gateway, False otherwise.
        """
        res = self.get(URL_GATEWAY.format(g=ip))
        if res.status_code != requests.codes.ok:
            return False

        LOGGER.info(f"{ip} is PowerView G3, now checking if Primary")
        res = self.get(URL_ROOMS.format(g=ip))
        if res.status_code == requests.codes.ok:
            LOGGER.info(f"{ip} is verified PowerView G3 Primary")
            return True

        LOGGER.error(f"{ip} is NOT PowerView G3 Primary")
        return False


    def _is_g2(self, ip):
        """Checks if the given IP address is a Gen 2 gateway.

        Args:
            ip (str): The IP address to check.

        Returns:
            bool: True if the IP belongs to a Gen 2 gateway, False otherwise.
        """
        res = self.get(URL_G2_HUB.format(g=ip))
        if res.status_code == requests.codes.ok:
            LOGGER.info(f"{ip} is PowerView 2")
            return True
        return False


    def poll(self, flag):
        """Handles polling requests from Polyglot.

        This method is called by Polyglot for both short and long polls.
        - Short polls are used for heartbeats, checking on background tasks, and
          triggering Gen 2 updates.
        - Long polls are used to trigger a full data refresh for Gen 3 gateways.

        Args:
            flag (str): A string indicating the type of poll ('shortPoll' or 'longPoll').
        """
        LOGGER.debug('enter')
        # no updates until node is through start-up
        if not self.ready_event:
            LOGGER.error(f"Node not ready yet, exiting")
            return
        
        # pause updates when in discovery
        if self.discovery_in == True:
            LOGGER.debug('exit, in discovery')
            return
        
        if 'shortPoll' in flag:
            LOGGER.debug(f"shortPoll controller")
            
            # only PowerView gen3 has sse server
            if self.generation == 2:
                self.pollUpdate()

            elif self.generation == 3:
                # start sse polling if not running for G3
                if not self.sse_client_in:
                    self.start_sse_client()
                # eventTimer has no purpose beyond an indicator of how long since the last event
                self.eventTimer += 1
                LOGGER.info(f"increment eventTimer = {self.eventTimer}")
            self.heartbeat()

            # start event polling loop    
            if not self.event_polling_in:
                self.start_event_polling()
                
        if 'longPoll' in flag:
            if self.generation == 3:
                self.pollUpdate()
                
        LOGGER.debug(f'exit')

        
    def pollUpdate(self):
        """Triggers a full data update from the gateway.

        This method fetches all room, shade, and scene data from the gateway
        and then seeds a 'home' event to trigger updates in the respective
        child nodes.
        """
        if self.poll_in:
            LOGGER.error(f"Still in Poll, exiting")
            return
        self.poll_in = True

        if not self.updateAllFromServer():
            LOGGER.error("Data collection error.")
            self.poll_in = False
            return

        # find the 'home' event
        event = next((e for e in self.gateway_event if e.get('evt') == 'home'), None)

        # clear out the old
        if event:
            self.remove_gateway_event(event)

        # bring in the new
        self.append_gateway_event({
            'evt': 'home',
            'shades': list(self.shades_map.keys()),
            'scenes': list(self.scenes_map.keys())
        })
        LOGGER.debug("Created new home event.")

        LOGGER.info(f"event(total) = {self.gateway_event}")
        self.poll_in = False

        
    def start_event_polling(self):
        """Starts the background thread for polling and processing gateway events.

        This ensures that the event processing loop is running in its own thread,
        consuming events that are queued by the SSE client.
        """
        LOGGER.debug(f"start")
        if self._event_polling_thread and self._event_polling_thread.is_alive():
            return  # Already running

        self.stop_sse_client_event.clear()
        self._event_polling_thread = Thread(
            target=self._poll_events,
            name="EventPollingThread",
            daemon=True
        )
        self._event_polling_thread.start()
        LOGGER.debug("exit")
        return


    def _poll_events(self):
        """The main loop for processing events from the gateway event queue.

        This method runs in a dedicated thread and continuously processes events
        such as 'homedoc-updated' and 'scene-add'. It also handles cleanup of
        stale or unhandled events.
        """
        
        self.event_polling_in = True

        while not self.stop_sse_client_event.is_set():
            # wait for events to process
            gateway_events = self.get_gateway_event()

            # find the 'message' event using next() with a default value.
            try:
                event = next((e for e in gateway_events
                              if e.get('message') == 'Not Found'), None)
            except Exception as ex:
                LOGGER.error(f"controller home event lookup error: {ex}", exc_info=True)
                event = None

            if event:
                LOGGER.error("Message Error, restart Event loop. Removing.")
                self.remove_gateway_event(event)
                self.stop_sse_client_event.set()
                break

            # find the 'home' event using next() with a default value.
            try:
                event = next((e for e in gateway_events
                              if e.get('evt') == 'home'), None)
            except Exception as ex:
                LOGGER.error(f"controller home event lookup error: {ex}", exc_info=True)
                event = None

            if event:
                if not event.get('shades') and not event.get('scenes'):
                        LOGGER.debug("Empty home event. Removing.")
                        self.remove_gateway_event(event)

            # handle the rest of events in isoDate order
            try:
                # filter events without isoDate like home
                event_nohome = (e for e in gateway_events if e.get('isoDate') is not None)
                # get most recent isoDate
                event = min(event_nohome, key=lambda x: x['isoDate'], default={})

            except (ValueError, TypeError) as ex: # Catch specific exceptions
                LOGGER.error(f"Error filtering or finding minimum event: {ex}")
                event = {}

            acted_upon = False

            # homedoc-updated
            if event.get('evt') == 'homedoc-updated':
                LOGGER.info('gateway event - homedoc-updated - {}'.format(event))
                self.remove_gateway_event(event)
                acted_upon = True

            # scene-add if scene does not already exist
            # PowerView app: scene-add can happen if user redefines scene or adds new one
            if event.get('evt') == 'scene-add':
                # check that scene does not exist
                match = any(sc == event.get('id') for sc in self.scenes_map.keys())
                if not match:
                    LOGGER.info(f'gateway event - scene-add, NEW so start Discover - {event}')
                    asyncio.run_coroutine_threadsafe(self.discover(), self.mainloop).result()
                self.remove_gateway_event(event)
                acted_upon = True

            #If not acted upon, remove if older than 2 minutes to prevent blocking of other events
            if not acted_upon and event:
                try:
                    # Compare the aware ISO date with the current aware UTC time
                    if check_timedelta_iso(event.get('isoDate'), minutes = 2):
                        LOGGER.warning(f"Unacted event!!! removed due to age > 2 min: {event}")
                        self.gateway_event.remove(event)
                except (TypeError, ValueError) as ex:
                    LOGGER.error(f"Invalid 'isoDate' in unacted event: {event}. Error: {ex}")
                    self.gateway_event.remove(event)
                    
        LOGGER.info(f"controller sse client event exiting while")                

            
    def start_sse_client(self):
        """Starts the SSE (Server-Sent Events) client.

        For Gen 3 gateways, this method initiates the asynchronous SSE client
        to listen for real-time events from the gateway.
        """
        LOGGER.debug(f"start")
        if self.generation == 3:
            self.stop_sse_client_event.clear()
            future = asyncio.run_coroutine_threadsafe(self._client_sse(), self.mainloop)
            LOGGER.info(f"sse client started: {future}")        

        LOGGER.debug("exit")        

    
    async def _client_sse(self):
        """The core asynchronous task for the SSE client.

        This async method connects to the gateway's SSE endpoint and listens for
        events indefinitely. It includes robust error handling and a retry
        mechanism with exponential backoff for connection issues.
        """
        self.sse_client_in = True
        LOGGER.info(f"controller start poll events")
                
        url = URL_EVENTS.format(g=self.gateway)
        retries = 0
        max_retries = 5
        base_delay = 1

        while not self.stop_sse_client_event.is_set():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        retries = 0  # Reset retries on successful connection
                        async for val in response.content:
                            line = val.decode().strip()
                            if not line:
                                continue

                            LOGGER.debug(f"Received: {line}")

                            try:
                                data = json.loads(line)
                                self.append_gateway_event(data)
                                LOGGER.info(f"new sse: {self.gateway_event}")
                                self.eventTimer = 0
                            except json.JSONDecodeError:
                                if line == "100 HELO":
                                    LOGGER.info(f"Pulse check: {line}")
                                else:
                                    LOGGER.error(f"Failed to decode JSON: <<{line}>>")
                            except Exception as ex:
                                LOGGER.error(f"sse client error: {ex}")

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                LOGGER.error(f"Connection to sse error: {e}")
                if retries >= max_retries:
                    LOGGER.error("Max retries reached. Stopping SSE client.")
                    break

                delay = base_delay * (2 ** retries)
                LOGGER.warning(f"Reconnecting in {delay}s")
                await asyncio.sleep(delay) # Explicitly use asyncio.sleep
                retries += 1
        LOGGER.info(f"controller sse client exiting due to while exit")

        
    def query(self, command = None):
        """Queries all nodes and reports their current status.

        This method is typically called by Polyglot in response to a 'Query'
        command from the ISY. It fetches the latest data from the gateway and
        then asks each child node to report its drivers.

        Args:
            command (dict, optional): The command payload from Polyglot.
                                      Defaults to None.
        """
        LOGGER.info(f"Enter {command}")
        if self.updateAllFromServer():
            nodes = self.poly.getNodes()
            for node in nodes:
                nodes[node].reportDrivers()
        LOGGER.debug(f"Exit")

        
    def updateProfile(self,command = None):
        """Initiates a profile update in Polyglot.

        This is typically called in response to an 'Update Profile' command
        from the ISY.

        Args:
            command (dict, optional): The command payload from Polyglot.
                                      Defaults to None.

        Returns:
            bool: The result of the profile update operation.
        """
        LOGGER.info(f"Enter {command}")
        st = self.poly.updateProfile()
        LOGGER.debug(f"Exit")
        return st

    
    def discover_cmd(self, command = None):
        """Handles the 'Discover' command from Polyglot.

        This method is a wrapper around the main `discover` async method,
        allowing it to be called from a synchronous command handler.

        Args:
            command (dict, optional): The command payload from Polyglot.
                                      Defaults to None.
        """
        LOGGER.info(f"Enter {command}")
        # run discover
        if asyncio.run_coroutine_threadsafe(self.discover(), self.mainloop).result():
            LOGGER.info(f"Success")
        else:
            LOGGER.error(f"Failure")
        LOGGER.debug(f"Exit")

            
    async def discover(self):
        """Discovers all shades and scenes from the gateway and creates nodes.

        This async method fetches all device data from the gateway, compares it
        with the existing nodes in Polyglot, and creates, updates, or removes
        nodes as necessary.

        Returns:
            bool: True if discovery was successful, False otherwise.
        """
        success = False
        if self.discovery_in:
            LOGGER.info('Discover already running.')
            return success

        self.discovery_in = True
        LOGGER.info("In Discovery...")

        nodes_existing = self.poly.getNodes()
        LOGGER.debug(f"current nodes = {nodes_existing}")
        nodes_old = [node for node in nodes_existing if node != 'hdctrl']
        nodes_new = []

        if self.updateAllFromServer():
            self._discover_shades(nodes_existing, nodes_new)
            self._discover_scenes(nodes_existing, nodes_new)
            self._cleanup_nodes(nodes_new, nodes_old)
            self.numNodes = len(nodes_new)
            self.setDriver('GV0', self.numNodes)
            LOGGER.debug(f"shades_array_map:  {self.shades_map}")
            LOGGER.debug(f"scenes_array_map:  {self.scenes_map}")
            success = True
        else:
            LOGGER.error('Discovery Failure')

        LOGGER.info(f"Discovery complete. success = {success}")
        self.discovery_in = False
        return success


    def _discover_shades(self, nodes_existing, nodes_new):
        """Discovers and creates nodes for shades.

        Args:
            nodes_existing (dict): A dictionary of existing nodes in Polyglot.
            nodes_new (list): A list to be populated with the addresses of
                              all discovered nodes.
        """
        for sh in self.shades_map:
            shade = self.shades_map[sh]
            shade_id = shade['id']
            shTxt = f"shade{shade_id}"
            capabilities = int(shade['capabilities'])

            nodes_new.append(shTxt)
            if shTxt not in nodes_existing:
                node = self._create_shade_node(shade, shTxt, capabilities)
                self.poly.addNode(node)
                self.wait_for_node_done()


    def _discover_scenes(self, nodes_existing, nodes_new):
        """Discovers and creates nodes for scenes.

        Args:
            nodes_existing (dict): A dictionary of existing nodes in Polyglot.
            nodes_new (list): A list to be populated with the addresses of
                              all discovered nodes.
        """
        for sc in self.scenes_map:
            scene = self.scenes_map[sc]
            scene_id = scene.get('id') or scene.get('_id')
            scTxt = f"scene{scene_id}"

            nodes_new.append(scTxt)
            if scTxt not in nodes_existing:
                node = Scene(self.poly, self.address, scTxt, scene["name"], scene_id)
                self.poly.addNode(node)
                self.wait_for_node_done()


    def _cleanup_nodes(self, nodes_new, nodes_old):
        """Removes any nodes that are no longer present on the gateway.

        Args:
            nodes_new (list): A list of node addresses that were found during
                              the current discovery process.
            nodes_old (list): A list of node addresses that existed before
                              the current discovery process.
        """
        nodes_db = self.poly.getNodesFromDb()
        LOGGER.debug(f"db nodes = {nodes_db}")

        nodes_current = self.poly.getNodes()
        nodes_get = {key: nodes_current[key] for key in nodes_current if key != self.id}

        LOGGER.debug(f"old nodes = {nodes_old}")
        LOGGER.debug(f"new nodes = {nodes_new}")
        LOGGER.debug(f"pre-delete nodes = {nodes_get}")

        for node in nodes_get:
            if node not in nodes_new:
                LOGGER.info(f"need to delete node {node}")
                self.poly.delNode(node)

        if set(nodes_get) == set(nodes_new):
            LOGGER.info('Discovery NO NEW activity')


    def _create_shade_node(self, shade, shTxt, capabilities):
        """Creates the appropriate shade node based on its capabilities.

        Args:
            shade (dict): The shade data from the gateway.
            shTxt (str): The node address for the new shade.
            capabilities (int): The capabilities code for the shade.

        Returns:
            Node: An instance of the appropriate Shade node class.
        """
        node_classes = {
            (7, 8): ShadeNoTilt,
            (0, 3): ShadeOnlyPrimary,
            (6,): ShadeOnlySecondary,
            (1, 2, 4): ShadeNoSecondary,
            (5,): ShadeOnlyTilt,
        }

        cls = next(
            (cls for caps, cls in node_classes.items() if capabilities in caps),
            Shade
        )
        return cls(self.poly, self.address, shTxt, shade["name"], shade["id"])


    def delete(self):
        """Handles node deletion from Polyglot.

        This method is called by Polyglot upon deletion of the NodeServer.
        If the process is co-resident and controlled by Polyglot, it will be
        terminated within 5 seconds of receiving this message. It sets the
        node status to off and stops background tasks.
        """
        self.setDriver('ST', 0, report = True, force = True)
        self.stop_sse_client_event.set()
        LOGGER.info('bye bye ... deleted.')


    def stop(self):
        """Handles the shutdown sequence for the node.

        This method is called by Polyglot when the NodeServer is stopped.
        It performs cleanup tasks such as setting the driver status to off
        and stopping background threads.
        """
        self.setDriver('ST', 0, report = True, force = True)
        self.stop_sse_client_event.set()
        self.Notices.clear()
        LOGGER.info('NodeServer stopped.')


    def heartbeat(self):
        """Sends a heartbeat signal to the ISY.

        This method alternates sending 'DON' and 'DOF' commands to the controller
        node, allowing ISY programs to monitor the NodeServer's status.
        """
        LOGGER.debug(f'heartbeat: hb={self.hb}')
        command = "DOF" if self.hb else "DON"
        self.reportCmd(command, 2)
        self.hb = not self.hb
        LOGGER.debug("Exit")


    def removeNoticesAll(self, command = None):
        """Removes all custom notices from the Polyglot dashboard.

        Args:
            command (dict, optional): The command payload from Polyglot.
                                      Defaults to None.
        """
        LOGGER.info(f"remove_notices_all: notices={self.Notices} , {command}")
        # Remove all existing notices
        self.Notices.clear()
        LOGGER.debug(f"Exit")


    def updateAllFromServer(self):
        """Fetches all data from the gateway for all nodes.

        This method throttles updates to avoid overloading the gateway. It calls
        the appropriate update method based on the gateway generation.

        Returns:
            bool: True if the update was successful, False otherwise.
        """
        success = True
        if self.update_in:
            return False
        if (time.perf_counter() > (self.update_last + self.update_minimum)):
            self.update_in = True
            self.last = time.perf_counter()
            if self.generation == 3:
                success = self.updateAllFromServerG3(self.getHomeG3())
                success = self.updateActiveFromServerG3(self.getScenesActiveG3())
            elif self.generation == 2:
                success = self.updateAllFromServerG2(self.getHomeG2())
            else:
                success = False
        self.update_in = False
        return success


    def updateAllFromServerG3(self, data):
        """Updates internal data maps from a Gen 3 gateway's home data.

        Parses the full data structure from a Gen 3 gateway, updating the
        internal maps for rooms, shades, and scenes.

        Args:
            data (dict): The 'home' data structure from the Gen 3 gateway.

        Returns:
            bool: True if the data was parsed successfully, False otherwise.
        """
        try:
            if data:
                self.rooms_map = {}
                self.scenes_map = {}

                for r in data["rooms"]:
                    LOGGER.debug('Update rooms')
                    room_name = r['name'][0:ROOM_NAME_LIMIT]
                    for sh in r["shades"]:
                        LOGGER.debug(f"Update shade {sh['id']}")
                        
                        name = base64.b64decode(sh.get('name', 'shade')).decode()
                        sh['name'] = self.poly.getValidName(('%s - %s') % (room_name, name))
                        LOGGER.debug(sh['name'])
                        if 'positions' in sh:
                            keys_to_convert = ['primary', 'secondary', 'tilt', 'velocity']
                            for key in keys_to_convert:
                                value = sh['positions'].get(key, 0)
                                sh['positions'][key] = self.toPercent(value)
                            # if non-existent or not 1-10 then set to default 0
                            capabilities = sh.get('capabilities')
                            if capabilities is None or capabilities not in range(1, 11):
                                sh['capabilities'] = 0                                
                        self.update_shade_data(sh['id'], sh)
                    self.rooms_map[r['_id']] = r

                LOGGER.info(f"rooms = {list(self.rooms_map.keys())}")
                LOGGER.info(f"shades = {list(self.shades_map.keys())}")

                for scene in data["scenes"]:
                    LOGGER.debug(f"update scenes {scene}")
                    name = scene['name']
                    if scene['room_Id'] == None:
                        room_name = "Multi"
                    else:
                        room_name = self.rooms_map.get(scene['room_Id'], {}).get('name', "Multi")[0:ROOM_NAME_LIMIT]
                    scene['name'] = self.poly.getValidName(f"{room_name} - {name}")
                    self.scenes_map[scene['_id']] = scene

                LOGGER.info(f"scenes = {list(self.scenes_map.keys())}")

                return True
            else:
                LOGGER.error('updateAllfromServerG3 error, no data')
                return False
        except Exception as ex:
            LOGGER.error(f"updateAllfromServerG3 error:{ex}", exc_info=True)
            return False

        
    def updateActiveFromServerG3(self, scenesActiveData):
        """Updates the list of currently active scenes from a Gen 3 gateway.

        Args:
            scenesActiveData (list[dict]): A list of active scene objects from
                                           the gateway.

        Returns:
            bool: True if the update was successful, False otherwise.
        """
        try:
            self.sceneIdsActive = []
            for sc in scenesActiveData:
                self.sceneIdsActive.append(sc["id"])
            self.sceneIdsActive.sort()
            LOGGER.info(f"activeScenes = {self.sceneIdsActive}")
            return True
        except:
            LOGGER.error("updateActiveFromServerG3 error")
            return False


    def getHomeG3(self):
        """Retrieves the main 'home' data object from a Gen 3 gateway.

        Returns:
            dict or None: The JSON response from the gateway as a dictionary,
                          or None if the request fails.
        """
        res = self.get(URL_HOME.format(g=self.gateway))
        code = res.status_code
        if self.gateways:
            if code == requests.codes.ok:
                data = res.json()
                LOGGER.info("getHomeG3 gateway good %s, %s", self.gateway, self.gateways)
                return data
            else:
                LOGGER.error("getHomeG3 gateway NOT good %s, %s", self.gateway, self.gateways)
        else:
            LOGGER.error("getHomeG3 self.gateways NONE")
        return None


    def getScenesActiveG3(self):
        """Retrieves the list of active scenes from a Gen 3 gateway.

        Returns:
            list[dict] or None: A list of active scene objects, or None if the
                                request fails.
        """
        res = self.get(URL_SCENES_ACTIVE.format(g=self.gateway))
        code = res.status_code
        if self.gateways:
            if code == requests.codes.ok:
                data = res.json()
                LOGGER.info("getScenesActiveG3 good %s, %s", self.gateway, self.gateways)
                return data
            else:
                LOGGER.error("getScenesActiveG3 NOT good %s, %s", self.gateway, self.gateways)
        else:
            LOGGER.error("getScenesActiveG3 self.gateways NONE")
        return None


    def updateAllFromServerG2(self, data):
        """Updates internal data maps by making multiple API calls to a Gen 2 hub.

        Unlike Gen 3, Gen 2 requires separate API calls to get room, shade,
        and scene data.

        Args:
            data (dict): The initial 'userdata' from the Gen 2 hub.

        Returns:
            bool: True if all data was fetched and parsed successfully,
                  False otherwise.
        """
        try:
            if data:
                self.rooms_map = {}
                self.scenes_map = {}

                res = self.get(URL_G2_ROOMS.format(g=self.gateway))
                if res.status_code == requests.codes.ok:
                    data = res.json()
                    for room in data['roomData']:
                        room['name'] = base64.b64decode(room['name']).decode()
                        self.rooms_map[room['id']] = room
                    LOGGER.info(f"rooms = {self.rooms_map.keys()}")
                    
                res = self.get(URL_G2_SHADES.format(g=self.gateway))
                if res.status_code == requests.codes.ok:
                    data = res.json()
                    for sh in data['shadeData']:
                        LOGGER.debug(f"Update shade {sh['id']}")
                        name = base64.b64decode(sh['name']).decode()
                        room_name = self.rooms_map[sh['roomId']]['name'][0:ROOM_NAME_LIMIT]
                        sh['name'] = self.poly.getValidName('%s - %s' % (room_name, name))
                        if 'positions' in sh:
                            pos = sh['positions']
                            # Use .get() to safely retrieve values and provide defaults
                            pos_kind1 = pos.get('posKind1')
                            position1 = pos.get('position1')
                            position2 = pos.get('position2')
                            
                            if pos_kind1 == 1 and position1 is not None:
                                pos['primary'] = self.toPercent(position1, G2_DIVR)
                            elif pos_kind1 == 3:
                                pos['primary'] = 0
                                if position1 is not None:
                                    pos['tilt'] = self.toPercent(position1, G2_DIVR)
    
                            if position2 is not None:
                                pos['secondary'] = self.toPercent(position2, G2_DIVR)

                            capabilities = sh.get('capabilities', 0)
                            if capabilities not in range(1, 11):
                                sh['capabilities'] = 0
                            
                        self.update_shade_data(sh['id'], sh)
                    LOGGER.info(f"shades = {list(self.shades_map.keys())}")
                    
                res = self.get(URL_G2_SCENES.format(g=self.gateway))
                if res.status_code == requests.codes.ok:
                    data = res.json()
                    for scene in data['sceneData']:
                        name = base64.b64decode(scene['name']).decode()
                        if scene['roomId'] == None:
                            room_name = "Multi"
                        else:
                            room_name = self.rooms_map[scene['roomId']]['name'][0:ROOM_NAME_LIMIT]
                        scene['name'] = self.poly.getValidName('%s - %s' % (room_name, name))
                        self.scenes_map[scene['id']] = scene

                    LOGGER.info(f"scenes = {list(self.scenes_map.keys())}")

                return True
            else:
                LOGGER.error(f"updateAllfromServerG2, no data")
                return False
        except Exception as ex:
            LOGGER.error(f'updateAllfromServerG2 error:{ex}')
            return False


    def getHomeG2(self):
        """Retrieves the main 'userdata' object from a Gen 2 gateway.

        Returns:
            dict or None: The JSON response from the gateway as a dictionary,
                          or None if the request fails.
        """
        res = self.get(URL_G2_HUB.format(g=self.gateway))
        code = res.status_code
        if self.gateways:
            if code == requests.codes.ok:
                data = res.json()
                LOGGER.info("getHomeG2 gateway good %s, %s", self.gateway, self.gateways)
                return data
            else:
                LOGGER.error("getHomeG2 gateway NOT good %s, %s", self.gateway, self.gateways)
        else:
            LOGGER.error("getHomeG2 self.gateways NONE")
        return None


    def get(self, url: str) -> requests.Response:
        """Performs an HTTP GET request with standardized error handling.

        Args:
            url (str): The URL to send the GET request to.

        Returns:
            requests.Response: The response object from the requests library.
                               If the request fails, a dummy response object
                               with an error status is returned.
        """
        try:
            res = requests.get(url, headers={'accept': 'application/json'})
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"Error fetching {url}: {e}")
            self.Notices['badfetch'] = "Error fetching from gateway"
            # Create a dummy response object with error info
            res = requests.Response()
            res.status_code = 300
            res._content = b'{"errMsg": "Error fetching from gateway, check configuration"}'
            return res

        status_handlers = {
            400: ("notPrimary", "Multi-Gateway environment - cannot determine primary"),
            503: ("HomeDoc", "PowerView Set-up not Complete See TroubleShooting Guide"),
        }

        if res.status_code in status_handlers:
            key, message = status_handlers[res.status_code]
            LOGGER.error(f"{message} ({url}): {res.status_code}")
            self.Notices[key] = message
            return res

        if res.status_code == 404:
            LOGGER.error(f"Gateway wrong {url}: {res.status_code}")
            return res

        if res.status_code != requests.codes.ok:
            LOGGER.error(f"Unexpected response fetching {url}: {res.status_code}")
            return res

        LOGGER.debug(f"Get from '{url}' returned {res.status_code}, response body '{res.text}'")

        # Clean up any previous notices
        for key in ['badfetch', 'notPrimary', 'HomeDoc']:
            self.Notices.delete(key)

        return res


    def toPercent(self, pos, divr=1.0):
        """Converts a raw position value to a percentage.

        Args:
            pos (int or float): The raw position value from the gateway.
            divr (float, optional): The divisor to use for the conversion.
                                    Defaults to 1.0 for Gen 3.

        Returns:
            int: The position converted to a percentage (0-100).
        """
        LOGGER.debug(f"{self.name}: toPercent:pos={pos}")
        if pos:
            newpos = math.trunc((float(pos) / divr * 100.0) + 0.5)
        else:
            newpos = pos
        LOGGER.debug(f"toPercent: pos={pos}, becomes {newpos}")
        return newpos


    def put(self, url: str, data: dict | None = None) -> dict | bool:
        """Performs an HTTP PUT request with standardized error handling.

        Args:
            url (str): The URL to send the PUT request to.
            data (dict, optional): The JSON payload to send with the request.
                                   Defaults to None.

        Returns:
            dict or bool: The JSON response from the gateway as a dictionary
                          if successful, otherwise False.
        """
        try:
            headers = {'accept': 'application/json'}
            res = requests.put(
                url,
                headers=headers,
                json=data if data is not None else None,
                timeout=10)

            if res.status_code != requests.codes.ok:
                LOGGER.error(f"Unexpected response in put {url}: {res.status_code}")
                LOGGER.debug(f"Response body: {res.text}")
                return False

            LOGGER.debug(f"Put to '{url}' succeeded with status {res.status_code}, response body: {res.text}")
            try:
                return res.json()
            except ValueError:
                LOGGER.error(f"Invalid JSON response from {url}")
                return False        

        except requests.exceptions.RequestException as e:
            LOGGER.error(f"Error in put {url} with data {data}: {e}", exc_info=True)
            return False

        
    # all the drivers - for reference
    # UOMs of interest:
    # 25: index
    # 107: Raw 1-byte unsigned value
    #
    # Driver controls of interest:
    # ST: Status
    # GV0: Custom Control 0
    drivers = [
        {'driver': 'ST', 'value': 1, 'uom': 25, 'name': "Controller Status"},
        {'driver': 'GV0', 'value': 0, 'uom': 107, 'name': "NumberOfNodes"},
    ]

    
    # Commands that this node can handle.  Should match the
    # 'accepts' section of the nodedef file.
    commands = {
        'QUERY': query,
        'DISCOVER': discover_cmd,
        'UPDATE_PROFILE': updateProfile,
        'REMOVE_NOTICES_ALL': removeNoticesAll,
    }
