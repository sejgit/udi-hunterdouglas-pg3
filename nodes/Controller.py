"""
udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2025 Stephen Jenkins

Controller class
"""


# std libraries
import asyncio, base64, json, logging, math, os, socket, time
from threading import Thread, Event, Lock, Condition

# external libraries
from udi_interface import Node, LOGGER, Custom, LOG_HANDLER # not used, ISY
import requests
import markdown2
import aiohttp

# personal libraries
from utils.node_funcs import get_valid_node_name # not using  get_valid_node_address as id's seem to behave
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
URL_ROOMS = 'http://{g}/home/rooms/{id}'
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

# We need an event loop as we run in a
# thread which doesn't have a loop
mainloop = asyncio.get_event_loop()


class Controller(Node):
    id = 'hdctrl'

    def __init__(self, poly, primary, address, name):
        """
        super
        self definitions
        data storage classes
        subscribes
        ready
        we exist!
        """
        super(Controller, self).__init__(poly, primary, address, name)
        # importand flags, timers, vars
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
        self.handler_params_st = None
        self.handler_data_st = None
        self.handler_typedparams_st = None
        self.handler_typeddata_st = None

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
        """
        Called by handler during startup.
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

        self.setParams()
        self.checkParams()

        self.gateway_sse = None

        configurationHelp = './POLYGLOT_CONFIG.md'
        if os.path.isfile(configurationHelp):
            cfgdoc = markdown2.markdown_path(configurationHelp)
            self.poly.setCustomParamsDoc(cfgdoc)

        # Wait for all handlers to finish
        LOGGER.warning(f'Waiting for all handlers to complete...')
        self.all_handlers_st_event.wait(timeout=60)
        if not self.all_handlers_st_event.is_set():
            LOGGER.error("Timed out waiting for handlers to startup")
            self.setDriver('ST', 2) # start-up failed
            return

        # Discover and wait for discovery to complete
        asyncio.run_coroutine_threadsafe(self.discover(), self.mainloop).result()

        # fist update
        if self.updateAllFromServer():
            with self.shades_map_lock:
                self.gateway_event.append({
                    'evt': 'home',
                    'shades': list(self.shades_map.keys()),
                    'scenes': list(self.scenes_map.keys())
                })
            LOGGER.debug(f"first update event[0]: {self.gateway_event[0]}")

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
        else:
            # start-up failed
            self.setDriver('ST', 2)
            LOGGER.error(f'START-UP FAILED!!! exit {self.name}')

        LOGGER.info(f'exit {self.name}')


    def node_queue(self, data):
        '''
        node_queue() and wait_for_node_done() create a simple way to wait
        for a node to be created.  The nodeAdd() API call is asynchronous and
        will return before the node is fully created. Using this, we can wait
        until it is fully created before we try to use it.
        '''
        address = data.get('address')
        if address:
            with self.queue_condition:
                self.n_queue.append(address)
                self.queue_condition.notify()


    def wait_for_node_done(self):
        """ See node_queue for comments."""
        with self.queue_condition:
            while not self.n_queue:
                self.queue_condition.wait(timeout = 0.2)
            self.n_queue.pop()


    def get_shade_data(self, sid):
        """
        self.shades_map: Encapsulate read access in a method
        """
        with self.shades_map_lock:
            return self.shades_map.get(sid)
        
    def update_shade_data(self, sid, data):
        """
        self.shades_map: Encapsulate write access in a method.
        """
        with self.shades_map_lock:
            if sid in self.shades_map:
                self.shades_map[sid].update(data)
            else:
                self.shades_map[sid] = data


    def append_gateway_event(self, event):
        """
        Called by sse to append to gateway_event array & signal that there is an event to process.
        """
        with self.gateway_event_condition:
            self.gateway_event.append(event)
            self.gateway_event_condition.notify_all()  # Wake up all waiting consumers


    def get_gateway_event(self) -> list[dict]:
        """
        Called by consumer fuctions (Controller, Shades, Scenes) to efficiently wait for events to process.
        """
        with self.gateway_event_condition:
            while not self.gateway_event:
                self.gateway_event_condition.wait()
            return self.gateway_event  # return reference, not a copy


    def remove_gateway_event(self, event):
        """
        Called by consumer functions (Controller, Shades, Scenes) to remove processed events.
        """
        with self.gateway_event_condition:
            if event in self.gateway_event:
                self.gateway_event.remove(event)

                
    def config_done(self):
        """
        For things we only do when have the configuration is loaded...
        """
        LOGGER.debug(f'enter')
        self.poly.addLogLevel('DEBUG_MODULES',9,'Debug + Modules')
        LOGGER.debug(f'exit')

        
    def dataHandler(self,data):
        LOGGER.debug(f'enter: Loading data {data}')
        if data is None:
            LOGGER.warning("No custom data")
        else:
            self.Data.load(data)
        self.handler_data_st = True
        self.check_handlers()

        
    def parameterHandler(self, params):
        """
        Called via the CUSTOMPARAMS event. When the user enters or
        updates Custom Parameters via the dashboard.
        """
        LOGGER.debug('Loading parameters now')
        if params:
            self.Parameters.update(params)
        
        defaults = {"gatewayip": "powerview-g3.local"}
        for param, default_value in defaults.items():
            if param not in self.Parameters:
                self.Parameters[param] = default_value

        cnt = 300
        while ((self.handler_data_st is None) and cnt > 0):
            LOGGER.warning(f'Waiting for Data: data={self.handler_data_st}... cnt={cnt}')
            time.sleep(1)
            cnt -= 1
        if cnt == 0:
            LOGGER.error("Timed out waiting for data to be loaded")
        while not self.checkParams():
            time.sleep(2)
        self.handler_params_st = True
        self.check_handlers()

        
    def setParams(self):
        """ Not used."""
        pass

    
    def typedParameterHandler(self, params):
        """
        Called via the CUSTOMTYPEDPARAMS event. This event is sent When
        the Custom Typed Parameters are created.  See the checkParams()
        below.  Generally, this event can be ignored.
        """
        LOGGER.debug('Loading typed parameters now')
        self.TypedParameters.load(params)
        LOGGER.debug(params)
        self.handler_typedparams_st = True
        self.check_handlers()

        
    def typedDataHandler(self, data):
        """
        Called via the CUSTOMTYPEDDATA event. This event is sent when
        the user enters or updates Custom Typed Parameters via the dashboard.
        'params' will be the full list of parameters entered by the user.
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
        """
        Once all start-up parameters are done then set event.
        """
        if (self.handler_params_st and self.handler_data_st and
                    self.handler_typedparams_st and self.handler_typeddata_st):
                self.all_handlers_st_event.set()

                
    def handleLevelChange(self, level):
        """
        Handle log level change.
        """
        LOGGER.info(f'enter: level={level}')
        if level['level'] < 10:
            LOGGER.info("Setting basic config to DEBUG...")
            LOG_HANDLER.set_basic_config(True,logging.DEBUG)
        else:
            LOGGER.info("Setting basic config to WARNING...")
            LOG_HANDLER.set_basic_config(True,logging.WARNING)
        LOGGER.info(f'exit: level={level}')

        
    def checkParams(self):
        """
        Check the custom parameters for the controller.
        This is using custom Params for gatewayip
        """
        self.Notices.delete('gateway')
        # gatewaycheck = self.gateway
        self.gateway = self.Parameters.gatewayip
        if self.gateway is None:
            self.gateway = URL_DEFAULT_GATEWAY
            LOGGER.info('checkParams: gateway not defined in customParams, using {}'.format(URL_DEFAULT_GATEWAY))
            self.Notices['gateway'] = 'Using default gateway local address; better to use a defined ip address.'
            return True
        try:
            if type(eval(self.gateway)) == list:
                self.gateways = eval(self.gateway)
                self.gateway = self.gateways[0]
        except:
            if type(self.gateway) == str:
                self.gateways.append(self.gateway)
            else:
                LOGGER.error('we have a bad gateway %s', self.gateway)
                self.Notices['gateway'] = 'Please note bad gateway address check gatewayip in customParams'
                return False
        if (self.goodip() and (self.genCheck3() or self.genCheck2())):
            LOGGER.info(f'good!! gateway:{self.gateway}, gateways:{self.gateways}')
            self.Notices.delete('gateway')
            self.Notices.delete('notPrimary')
            return True
        else:
            LOGGER.info(f"checkParams: no gateway found in {self.gateways}")
            self.Notices['gateway'] = 'Please note no primary gateway found in gatewayip'
            return False

        
    def goodip(self):
        """
        Check for valid ip in gateway address.
        """
        good = True
        for ip in self.gateways:
            try:
                socket.inet_aton(ip)
            except socket.error:
                good = False
                LOGGER.error('we have a bad gateway ip address %s', ip)
                self.Notices['gateway'] = 'Please note bad gateway address check gatewayip in customParams'
        return good

    
    def genCheck3(self):
        """
        Check for a Generation 3 gateway.
        """
        for ip in self.gateways:
            res = self.get(URL_GATEWAY.format(g=ip))
            if res.status_code == requests.codes.ok:
                LOGGER.info(f"{ip} is PowerView G3")
                res = self.get(URL_HOME.format(g=ip))
                if res.status_code == requests.codes.ok:
                    LOGGER.info(f"{ip} is PowerView G3 Primary")
                    self.gateway = ip
                    self.generation = 3
                    return True
        return False

    
    def genCheck2(self):
        """
        Check for a Generation 2 gateway.
        """
        for ip in self.gateways:
            res = self.get(URL_G2_HUB.format(g=ip))
            if res.status_code == requests.codes.ok:
                LOGGER.info(f"{ip} is PowerView 2")
                self.gateway = ip
                self.generation = 2
                return True
        return False

    
    def poll(self, flag):
        """
        Wait until all start-up is ready, and pause if in discovery.
        use longPoll for Gen3 update through gateway GET 
        use shortPoll for Gen2 update through gateway GET,
                      as well as heart-beat,
                      and starting / restarting of sse client,
                      and starting / restarting of polling event client,
                      and incrementing clock since last event from sse server
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

            else:
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
        """
        Handles poll GET updates from gateway as well as seeding shade/scene update events
        which command the shade/scene nodes to take the updated data and apply it.
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
        """
        Run routine in a separate thread to retrieve events from array loaded by sse client from gateway.
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
        """
        Handles Gateway Events like homedoc-updated & scene-add (for new scenes)
        Removes unacted events only if isoDate is older than 2 minutes or invalid.
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
        """
        Run sse client in a thread-safe loop for gateway events polling which then loads the events to an array.
        """
        LOGGER.debug(f"start")
        if self.generation == 3:
            self.stop_sse_client_event.clear()
            future = asyncio.run_coroutine_threadsafe(self._client_sse(), self.mainloop)
            LOGGER.info(f"sse client started: {future}")        

        LOGGER.debug("exit")        

    
    async def _client_sse(self):
        """
        Polls the SSE endpoint with aiohttp for events.
        Includes robust retry logic with exponential backoff.
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
        """
        Query all nodes from the gateway.
        """
        LOGGER.info(f"Enter {command}")
        if self.updateAllFromServer():
            nodes = self.poly.getNodes()
            for node in nodes:
                nodes[node].reportDrivers()
        LOGGER.debug(f"Exit")

        
    def updateProfile(self,command = None):
        """
        Update the profile.
        """
        LOGGER.info(f"Enter {command}")
        st = self.poly.updateProfile()
        LOGGER.debug(f"Exit")
        return st

    
    def discover_cmd(self, command = None):
        """
        Run Discover from command.
        """
        LOGGER.info(f"Enter {command}")
        # force a gateway check
        self.checkParams()
        
        # run discover
        if asyncio.run_coroutine_threadsafe(self.discover(), self.mainloop).result():
            LOGGER.info(f"Success")
        else:
            LOGGER.error(f"Failure")
        LOGGER.debug(f"Exit")

        
    async def discover(self):
        """
        Discover all nodes from the gateway.
        """
        success = False
        if self.discovery_in:
            LOGGER.info('Discover already running.')
            return success

        self.discovery_in = True
        LOGGER.info(f"In Discovery...")

        nodes = self.poly.getNodes()
        LOGGER.debug(f"current nodes = {nodes}")
        nodes_old = []
        for node in nodes:
            LOGGER.debug(f"current node = {node}")
            if node != 'hdctrl':
                nodes_old.append(node)

        nodes_new = []
        if self.updateAllFromServer():
            for sh in self.shades_map.keys():
                shade = self.shades_map[sh]
                shadeId = shade['id']

                shTxt = f"shade{shadeId}"
                nodes_new.append(shTxt)
                capabilities = int(shade['capabilities'])
                if shTxt not in nodes:
                    if capabilities in [7, 8]:
                        self.poly.addNode(ShadeNoTilt(self.poly,
                                                self.address,
                                                shTxt,
                                                shade["name"],
                                                shadeId))
                    elif capabilities in [0, 3]:
                        self.poly.addNode(ShadeOnlyPrimary(self.poly,
                                                self.address,
                                                shTxt,
                                                shade["name"],
                                                shadeId))
                    elif capabilities in [6]:
                        self.poly.addNode(ShadeOnlySecondary(self.poly,
                                                self.address,
                                                shTxt,
                                                shade["name"],
                                                shadeId))
                    elif capabilities in [1, 2, 4]:
                        self.poly.addNode(ShadeNoSecondary(self.poly,
                                                self.address,
                                                shTxt,
                                                shade["name"],
                                                shadeId))
                    elif capabilities in [5]:
                        self.poly.addNode(ShadeOnlyTilt(self.poly,
                                                self.address,
                                                shTxt,
                                                shade["name"],
                                                shadeId))
                    else: # [9, 10] or else
                        self.poly.addNode(Shade(self.poly,
                                                self.address,
                                                shTxt,
                                                shade["name"],
                                                shadeId))
                    self.wait_for_node_done()

            for sc in self.scenes_map.keys():
                scene = self.scenes_map[sc]
                if self.generation == 2:
                    sceneId = scene['id']
                else:
                    sceneId = scene['_id']

                scTxt = f"scene{sceneId}"
                nodes_new.append(scTxt)
                if scTxt not in nodes:
                    self.poly.addNode(Scene(self.poly,
                                            self.address,
                                            scTxt,
                                            scene["name"],
                                            sceneId))
                    self.wait_for_node_done()
        else:
            LOGGER.error('Discovery Failure')
            self.discovery_in = False
            return success

        if not (nodes_new == []):
            # remove nodes which do not exist in gateway
            nodes = self.poly.getNodesFromDb()
            LOGGER.debug(f"db nodes = {nodes}")
            nodes = self.poly.getNodes()
            nodes_get = {key: nodes[key] for key in nodes if key != self.id}
            LOGGER.debug(f"old nodes = {nodes_old}")
            LOGGER.debug(f"new nodes = {nodes_new}")
            LOGGER.debug(f"pre-delete nodes = {nodes_get}")
            for node in nodes_get:
                if (node not in nodes_new):
                    LOGGER.info(f"need to delete node {node}")
                    self.poly.delNode(node)
            if nodes_get == nodes_new:
                LOGGER.info('Discovery NO NEW activity')
            self.numNodes = len(nodes_get)
            self.setDriver('GV0', self.numNodes)
            success = True
            LOGGER.debug(f"shades_array_map:  {self.shades_map}")
            LOGGER.debug(f"scenes_array_map:  {self.scenes_map}")
        LOGGER.info(f"Discovery complete. success = {success}")
        self.discovery_in = False
        return success

    
    def delete(self):
        """
        This is called by Polyglot upon deletion of the NodeServer. If the
        process is co-resident and controlled by Polyglot, it will be
        terminiated within 5 seconds of receiving this message.
        """
        self.setDriver('ST', 0, report = True, force = True)
        self.stop_sse_client_event.set()
        LOGGER.info('bye bye ... deleted.')

        
    def stop(self):
        """
        This is called by Polyglot when the node server is stopped.  You have
        the opportunity here to cleanly disconnect from your device or do
        other shutdown type tasks.
        """
        self.setDriver('ST', 0, report = True, force = True)
        self.stop_sse_client_event.set()
        self.Notices.clear()
        LOGGER.info('NodeServer stopped.')

        
    def heartbeat(self):
        """
        Heartbeat function uses the long poll interval to alternately send a ON and OFF
        command back to the ISY.  Programs on the ISY can then monitor this.
        """
        LOGGER.debug(f'heartbeat: hb={self.hb}')
        command = "DOF" if self.hb else "DON"
        self.reportCmd(command, 2)
        self.hb = not self.hb
        LOGGER.debug("Exit")

        
    def removeNoticesAll(self, command = None):
        """
        Remove all notices from the ISY.
        """
        LOGGER.info(f"remove_notices_all: notices={self.Notices} , {command}")
        # Remove all existing notices
        self.Notices.clear()
        LOGGER.debug(f"Exit")

        
    def updateAllFromServer(self):
        """
        Update all nodes from the gateway.
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
        """
        Update all nodes from the gateway for Generation 3.
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
                        sh['name'] = get_valid_node_name(('%s - %s') % (room_name, name))
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
                    scene['name'] = get_valid_node_name(f"{room_name} - {name}")
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
        """
        Update active scene array from data previously retrieved.
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
        """
        Get the home data from the gateway for Generation 3.
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
                if self.genCheck3():
                    LOGGER.error("getHomeG3 fixed %s, %s", self.gateway, self.gateways)
                else:
                    LOGGER.error("getHomeG3 still NOT fixed %s, %s", self.gateway, self.gateways)
        else:
            LOGGER.error("getHomeG3 self.gateways NONE")
        return None

    
    def getScenesActiveG3(self):
        """
        Get the active scenes from the gateway for Generation 3.
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
        """
        Update all nodes from the gateway for Generation 2.
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
                        sh['name'] = get_valid_node_name('%s - %s' % (room_name, name))
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
                        scene['name'] = get_valid_node_name('%s - %s' % (room_name, name))
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
        """
        Get the home data from the gateway for Generation 2.
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
                if self.genCheck2():
                    LOGGER.error("getHomeG2 fixed %s, %s", self.gateway, self.gateways)
                else:
                    LOGGER.error("getHomeG2 still NOT fixed %s, %s", self.gateway, self.gateways)
        else:
            LOGGER.error("getHomeG2 self.gateways NONE")
        return None

    
    def get(self, url):
        """
        Get data from the specified URL.
        """
        res = None
        try:
            res = requests.get(url, headers={'accept': 'application/json'})
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"Error fetching {url}: {e}")
            res = requests.Response()
            res.status_code = 300
            res.raw = {"errMsg":"Error fetching from gateway, check configuration"}
            self.Notices['badfetch'] = "Error fetching from gateway"
            return res
        if res.status_code == 400:
            LOGGER.error(f"Check if not primary {url}: {res.status_code}")
            self.Notices['notPrimary'] = "Multi-Gateway environment - cannot determine primary"
            return res
        if res.status_code == 404:
            LOGGER.error(f"Gateway wrong {url}: {res.status_code}")
            return res
        if res.status_code == 503:
            LOGGER.error(f"HomeDoc not set-up {url}: {res.status_code}")
            self.Notices['HomeDoc'] = "PowerView Set-up not Complete See TroubleShooting Guide"
            return res
        elif res.status_code != requests.codes.ok:
            LOGGER.error(f"Unexpected response fetching {url}: {res.status_code}")
            return res
        else:
            LOGGER.debug(f"Get from '{url}' returned {res.status_code}, response body '{res.text}'")
        self.Notices.delete('badfetch')
        self.Notices.delete('notPrimary')
        self.Notices.delete('HomeDoc')
        return res

    
    def toPercent(self, pos, divr=1.0):
        """
        Convert a position to a percentage.
        """
        LOGGER.debug(f"{self.name}: toPercent:pos={pos}")
        if pos:
            newpos = math.trunc((float(pos) / divr * 100.0) + 0.5)
        else:
            newpos = pos
        LOGGER.debug(f"toPercent: pos={pos}, becomes {newpos}")
        return newpos

    
    def put(self, url, data=None):
        """
        Put data to the specified URL.
        """
        res = None
        try:
            if data:
                res = requests.put(url, json=data, headers={'accept': 'application/json'})
            else:
                res = requests.put(url, headers={'accept': 'application/json'})

        except requests.exceptions.RequestException as e:
            LOGGER.error(f"Error in put {url} with data {data}: {e}", exc_info=True)
            if res:
                LOGGER.debug(f"Put from '{url}' returned {res.status_code}, response body '{res.text}'")
            return False

        if res and res.status_code != requests.codes.ok:
            LOGGER.error('Unexpected response in put %s: %s' % (url, str(res.status_code)))
            LOGGER.debug(f"Put from '{url}' returned {res.status_code}, response body '{res.text}'")
            return False

        response = res.json()
        LOGGER.debug(f"Put from '{url}' returned {res.status_code}, response body '{res.text}'")
        return response


    # Status that this node has. Should match the 'sts' section
    # of the nodedef file.
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
