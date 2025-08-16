"""
udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

Controller class
"""

# std libraries
import asyncio, base64, json, logging, math, os, socket, time
from threading import Thread, Event

# external libraries
from udi_interface import Node, LOGGER, Custom, LOG_HANDLER # not used, ISY
import requests
import markdown2
import aiohttp

# personal libraries
from node_funcs import get_valid_node_name # not using  get_valid_node_address as id's seem to behave

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
        self.ready = False
        self.pollingBypass = False # debug purposes: set true to skip polling
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
        self.discover_done = False
        self.poll_in = False
        self.sse_polling_in = False
        
        # storage arrays
        self.n_queue = []
        self.gateway_array = []
        self.gateway_event = [{'evt': 'home', 'shades': [], 'scenes': []}]
        self.rooms_array = []
        self.roomIds_array = []
        self.shades_array = []
        self.shadeIds_array = []
        self.scenes_array = []
        self.sceneIds_array = []
        self.tiltCapable = [1, 2, 4, 5, 9, 10] # shade types
        self.tiltOnly90Capable = [1, 9]

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
        self.poly.subscribe(self.poly.DISCOVER,          self.discover)
        self.poly.subscribe(self.poly.CUSTOMTYPEDDATA,   self.typedDataHandler)
        self.poly.subscribe(self.poly.CUSTOMTYPEDPARAMS, self.typedParameterHandler)
        self.poly.subscribe(self.poly.ADDNODEDONE,       self.node_queue)

        # Tell the interface we have subscribed to all the events we need.
        # Once we call ready(), the interface will start publishing data.
        self.poly.ready()

        # Tell the interface we exist.  
        self.poly.addNode(self, conn_status='ST')

    def node_queue(self, data):
        '''
        node_queue() and wait_for_node_event() create a simple way to wait
        for a node to be created.  The nodeAdd() API call is asynchronous and
        will return before the node is fully created. Using this, we can wait
        until it is fully created before we try to use it.
        '''
        self.n_queue.append(data['address'])

    def wait_for_node_done(self):
        while len(self.n_queue) == 0:
            time.sleep(0.2)
        self.n_queue.pop()

    def start(self):
        """
        Called by handler during startup.
        """
        LOGGER.info(f"Started HunterDouglas PG3 NodeServer {self.poly.serverdata['version']}")
        self.Notices.clear()
        self.Notices['hello'] = 'Plugin Start-up'
        self.update_last = 0.0

        # Send the profile files to the ISY if neccessary or version changed.
        self.poly.updateProfile()

        # Send the default custom parameters documentation file to Polyglot
        self.poly.setCustomParamsDoc()

        # Initializing heartbeat
        self.setDriver('ST', 1)
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
        #
        # Wait for all handlers to finish
        #
        cnt = 600
        while ((self.handler_params_st is None or self.handler_data_st is None
                or self.handler_typedparams_st is None or self.handler_typeddata_st is None) and cnt > 0):
            LOGGER.warning(f'Waiting for all: params={self.handler_params_st} data={self.handler_data_st}... cnt={cnt}')
            time.sleep(1)
            cnt -= 1
        if cnt == 0:
            LOGGER.error("Timed out waiting for handlers to startup")

        # Discover
        if self.discover():
            while self.discovery_in == True:
                time.sleep(1)
        else:
            LOGGER.error(f'discover failed exit NODE!!', exc_info=True)
            return

        # fist update
        if self.updateAllFromServer():
            self.gateway_event[0]['shades'] = self.shadeIds_array
            self.gateway_event[0]['scenes'] = self.sceneIds_array
            # clear inital start-up message
            if self.Notices['hello']:
                self.Notices.delete('hello')
            self.ready = True

        LOGGER.info(f'exit {self.name}')

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

    def parameterHandler(self, params):
        """
        Called via the CUSTOMPARAMS event. When the user enters or
        updates Custom Parameters via the dashboard.
        """
        LOGGER.debug('Loading parameters now')
        self.Parameters.load(params)
        defaults = {"gatewayip": "powerview-g3.local"}
        for param in defaults:
            if params is None or not param in params:
                self.Parameters[param] = defaults[param]
                return
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

    def setParams(self):
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
                self.gateway_array = eval(self.gateway)
                self.gateway = self.gateway_array[0]
        except:
            if type(self.gateway) == str:
                self.gateway_array.append(self.gateway)
            else:
                LOGGER.error('we have a bad gateway %s', self.gateway)
                self.Notices['gateway'] = 'Please note bad gateway address check gatewayip in customParams'
                return False
        if (self.goodip() and (self.genCheck3() or self.genCheck2())):
            LOGGER.info('good self.gateway_array %s', self.gateway_array)
            LOGGER.info("good self.gateway = %s", self.gateway)
            self.Notices.delete('gateway')
            self.Notices.delete('notPrimary')
            return True
        else:
            LOGGER.info(f"checkParams: no gateway found in {self.gateway_array}")
            self.Notices['gateway'] = 'Please note no primary gateway found in gatewayip'
            return False
                                
    def goodip(self):
        """
        Check for valid ip in gateway address.
        """
        good = True
        for ip in self.gateway_array:
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
        for ip in self.gateway_array:
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
        for ip in self.gateway_array:
            res = self.get(URL_G2_HUB.format(g=ip))
            if res.status_code == requests.codes.ok:
                LOGGER.info(f"{ip} is PowerView 2")
                self.gateway = ip
                self.generation = 2
                return True
        return False
            
    """
    Called POLL event is triggerd at the intervals specified
    in the node server configuration, long poll and a short poll.
    """
    def poll(self, polltype):
        LOGGER.debug('enter')
        # no updates until node is through start-up
        if not self.ready:
            LOGGER.error(f"Node not ready yet, exiting")
            return            
        # pause updates when in discovery
        if self.discovery_in == True:
            LOGGER.debug('exit, in discovery')
            return
        if polltype == 'longPoll':
            if self.generation == 3:
                self.pollUpdate()
        else:
            self.heartbeat()
            # only PowerView gen3 has sse server
            if self.generation == 2:
                self.pollUpdate()
            else:
                # start sse polling if not running for G3
                if not self.sse_polling_in:
                    self.start_SSE_polling()
                # eventTimer has no purpose beyond an indicator of how long since the last event
                self.eventTimer += 1
                LOGGER.info(f"increment eventTimer = {self.eventTimer}")        
        LOGGER.debug('exit')
        
    def pollUpdate(self):
        """
        Handles poll updates from gateway as well as seeding shade/scene update events
        """
        if self.poll_in:
            LOGGER.error(f"Still in Poll, exiting")
            return
        self.poll_in = True
        LOGGER.debug('longPoll re-parse updateallfromserver (controller)')
        if not self.pollingBypass:
            if self.updateAllFromServer():
                LOGGER.debug(f"self.gateway_event: {self.gateway_event}")
                try:
                    event = list(filter(lambda events: events['evt'] == 'homedoc-updated', self.gateway_event))
                    if event:
                        event = event[0]
                        LOGGER.info('longPoll event - homedoc-updated - {}'.format(event))
                        self.gateway_event.remove(event)

                    event = list(filter(lambda events: events['evt'] == 'home', self.gateway_event))
                    if event:
                        event = event[0]
                        self.gateway_event[self.gateway_event.index(event)]['shades'] = self.shadeIds_array
                        self.gateway_event[self.gateway_event.index(event)]['scenes'] = self.sceneIds_array
                        LOGGER.debug('longPoll trigger nodes {}'.format(self.gateway_event))
                    else:
                        self.gateway_event.append({'evt': 'home', 'shades': [], 'scenes': []})
                        LOGGER.debug('longPoll reset {}'.format(self.gateway_event))
                except:
                    LOGGER.error("LongPoll event error")
                LOGGER.info("event(total) = {}".format(self.gateway_event))
            else:
                LOGGER.error(f"data collection error")
        else:
            LOGGER.error(f"data pollingBypass:{self.pollingBypass}")
        self.poll_in = False

    async def _poll_sse(self):
        self.sse_polling_in = True
        url = URL_EVENTS.format(g=self.gateway)
        self.max_retries = 5
        self.base_delay = 1
        retries = 0
        while not Event().is_set():
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        retries = 0
                        async for val in response.content:
                            LOGGER.debug(f"Received: {val.decode().strip()}")
                            if val:
                                if val == "100HELO":
                                    continue
                                try:
                                    self.gateway_event.append(json.loads(val))
                                    LOGGER.info(f"new sse: {self.gateway_event}")
                                    self.eventTimer = 0
                                except:
                                    LOGGER.debug(f"noadd:{val.decode().strip()}")
                                    pass

            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                LOGGER.error(f"Connection to sse error: {e}")
                if retries >= self.max_retries:
                    LOGGER.error("Max retries reached. Stopping SSE client.")
                    self.sse_polling_in = False
                    break
                delay = self.base_delay * (2 ** retries)
                LOGGER.error(f"Reconnecting in {delay}s")
                await asyncio.sleep(delay)
                retries += 1
        self.sse_polling_in = False
                        
    def start_SSE_polling(self):
            future = asyncio.run_coroutine_threadsafe(self._poll_sse(), self.mainloop)
            return future

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
        while not self.checkParams():
            time.sleep(2)
        # run discover
        if self.discover():
            LOGGER.info(f"Success")
        else:
            LOGGER.error(f"Failure")
        LOGGER.debug(f"Exit")
        
    def discover(self):
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
            for shade in self.shades_array:
                if self.generation == 2:
                    shadeId = shade['id']
                else:
                    shadeId = shade['shadeId']

                shTxt = f"shade{shadeId}"
                nodes_new.append(shTxt)
                try:
                    capabilities = int(shade['capabilities'])
                except:
                    LOGGER.error(f"no capabilties defined, use default shade")
                    capabilities = int(0)
                if shTxt not in nodes:
                    if capabilities in [7, 8]:
                        self.poly.addNode(ShadeNoTilt(self.poly, \
                                                self.address, \
                                                shTxt, \
                                                shade["name"], \
                                                shade))
                    elif capabilities in [0, 3]:
                        self.poly.addNode(ShadeOnlyPrimary(self.poly, \
                                                self.address, \
                                                shTxt, \
                                                shade["name"], \
                                                shade))
                    elif capabilities in [6]:
                        self.poly.addNode(ShadeOnlySecondary(self.poly, \
                                                self.address, \
                                                shTxt, \
                                                shade["name"], \
                                                shade))
                    elif capabilities in [1, 2, 4]:
                        self.poly.addNode(ShadeNoSecondary(self.poly, \
                                                self.address, \
                                                shTxt, \
                                                shade["name"], \
                                                shade))
                    elif capabilities in [5]:
                        self.poly.addNode(ShadeOnlyTilt(self.poly, \
                                                self.address, \
                                                shTxt, \
                                                shade["name"], \
                                                shade))
                    else: # [9, 10] or else
                        self.poly.addNode(Shade(self.poly, \
                                                self.address, \
                                                shTxt, \
                                                shade["name"], \
                                                shade))
                    self.wait_for_node_done()
                
            for scene in self.scenes_array:
                if self.generation == 2:
                    sceneId = scene['id']
                else:
                    sceneId = scene['_id']
                
                scTxt = f"scene{sceneId}"
                nodes_new.append(scTxt)
                if scTxt not in nodes:
                    self.poly.addNode(Scene(self.poly, \
                                            self.address, \
                                            scTxt, \
                                            scene["name"], \
                                            sceneId))
                    self.wait_for_node_done()
        else:
            LOGGER.error('Discovery Failure')
            self.discovery_in = False
            return success

        if not (nodes_new == []):
            # remove nodes which do not exist in gateway
            nodes = self.poly.getNodesFromDb()
            LOGGER.info(f"db nodes = {nodes}")
            nodes = self.poly.getNodes()
            nodes_get = {key: nodes[key] for key in nodes if key != self.id}
            LOGGER.info(f"old nodes = {nodes_old}")
            LOGGER.info(f"new nodes = {nodes_new}")
            LOGGER.info(f"pre-delete nodes = {nodes_get}")
            for node in nodes_get:
                if (node not in nodes_new):
                    LOGGER.info(f"need to delete node {node}")
                    self.poly.delNode(node)
            if nodes_get == nodes_new:
                LOGGER.info('Discovery NO NEW activity')
            self.numNodes = len(nodes_get)
            self.setDriver('GV0', self.numNodes)
            success = True
        LOGGER.info(f"Discovery complete. success = {success}")
        self.discovery_in = False
        return success

    def delete(self):
        """
        This is called by Polyglot upon deletion of the NodeServer. If the
        process is co-resident and controlled by Polyglot, it will be
        terminiated within 5 seconds of receiving this message.
        """
        LOGGER.info('bye bye ... deleted.')

    def stop(self):
        """
        This is called by Polyglot when the node server is stopped.  You have
        the opportunity here to cleanly disconnect from your device or do
        other shutdown type tasks.
        """
        self.Notices.clear()
        LOGGER.info('NodeServer stopped.')

    def heartbeat(self):
        """
        Heartbeat function uses the long poll interval to alternately send a ON and OFF
        command back to the ISY.  Programs on the ISY can then monitor this.
        """
        LOGGER.debug(f'heartbeat: hb={self.hb}')
        if self.hb == 0:
            self.reportCmd("DON",2)
            self.hb = 1
        else:
            self.reportCmd("DOF",2)
            self.hb = 0
        LOGGER.debug(f"Exit")

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
                self.rooms_array = []
                self.roomIds_array = []
                self.shades_array = []
                self.shadeIds_array = []
                self.scenes_array = []
                self.sceneIds_array = []

                for r in data["rooms"]:
                    LOGGER.debug('Update rooms')
                    self.roomIds_array.append(r['_id'])
                    self.rooms_array.append(r)
                    room_name = r['name']
                    room_name = room_name[0:ROOM_NAME_LIMIT]
                    for sh in r["shades"]:
                        LOGGER.debug(f"Update shade {sh['id']}")
                        sh['shadeId'] = sh['id']
                        name = base64.b64decode(sh.pop('name')).decode()
                        sh['name'] = get_valid_node_name(('%s - %s') % (room_name, name))
                        LOGGER.debug(sh['name'])
                        if 'positions' in sh:
                            positions = sh['positions']
                            # Convert positions to integer percentages
                            if 'primary' in positions:
                                sh['positions']['primary'] = self.toPercent(positions['primary'])
                            if 'secondary' in positions:
                                sh['positions']['secondary'] = self.toPercent(positions['secondary'])
                            if 'tilt' in positions:
                                sh['positions']['tilt'] = self.toPercent(positions['tilt'])
                            if 'velocity' in positions:
                                sh['positions']['velocity'] = self.toPercent(positions['velocity'])
                        self.shadeIds_array.append(sh["shadeId"])
                        self.shades_array.append(sh)

                LOGGER.info(f"rooms = {self.roomIds_array}")
                LOGGER.info(f"shades = {self.shadeIds_array}")

                for sc in data["scenes"]:
                    LOGGER.debug(f"update scenes {sc}")
                    self.sceneIds_array.append(sc["_id"])
                    self.scenes_array.append(sc)
                    name = sc['name']
                    LOGGER.debug("scenes-3")
                    if sc['room_Id'] == None:
                        room_name = "Multi"
                    else:
                        room_name = self.rooms_array[self.roomIds_array.index(sc['room_Id'])]['name']
                        room_name = room_name[0:ROOM_NAME_LIMIT]
                    sc['name'] = get_valid_node_name('%s - %s' % (room_name, name))
                    LOGGER.debug('Update scenes-1')

                LOGGER.info(f"scenes = {self.sceneIds_array}")

                self.no_update = False
                return True
            else:
                self.no_update = False
                return False
        except:
            LOGGER.error('Update error')
            self.no_update = False
            return False

    def updateActiveFromServerG3(self, scenesActiveData):
        try:
            self.sceneIdsActive_array = []
            for sc in scenesActiveData:
                self.sceneIdsActive_array.append(sc["id"])
            LOGGER.info(f"activeScenes = {self.sceneIdsActive_array}")
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
        if self.gateway_array:
            if code == requests.codes.ok:
                data = res.json()
                LOGGER.info("getHomeG3 gateway good %s, %s", self.gateway, self.gateway_array)
                return data
            else:
                LOGGER.error("getHomeG3 gateway NOT good %s, %s", self.gateway, self.gateway_array)
                if self.genCheck3():
                    LOGGER.error("getHomeG3 fixed %s, %s", self.gateway, self.gateway_array)
                else:
                    LOGGER.error("getHomeG3 still NOT fixed %s, %s", self.gateway, self.gateway_array)
        else:
            LOGGER.error("getHomeG3 self.gateway_array NONE")
        return None

    def getScenesActiveG3(self):
        """
        Get the active scenes from the gateway for Generation 3.
        """
        res = self.get(URL_SCENES_ACTIVE.format(g=self.gateway))
        code = res.status_code
        if self.gateway_array:
            if code == requests.codes.ok:
                data = res.json()
                LOGGER.info("getScenesActiveG3 good %s, %s", self.gateway, self.gateway_array)
                return data
            else:
                LOGGER.error("getScenesActiveG3 NOT good %s, %s", self.gateway, self.gateway_array)
        else:
            LOGGER.error("getScenesActiveG3 self.gateway_array NONE")
        return None

    def updateAllFromServerG2(self, data):
        """
        Update all nodes from the gateway for Generation 2.
        """
        try:
            if data:
                self.rooms_array = []
                self.roomIds_array = []
                self.shades_array = []
                self.shadeIds_array = []
                self.scenes_array = []
                self.sceneIds_array = []

                res = self.get(URL_G2_ROOMS.format(g=self.gateway))
                if res.status_code == requests.codes.ok:
                    data = res.json()
                    self.rooms_array = data['roomData']
                    self.roomIds_array = data['roomIds']
                    for room in self.rooms_array:
                        room['name'] = base64.b64decode(room['name']).decode()
                    LOGGER.info(f"rooms = {self.roomIds_array}")
                    
                res = self.get(URL_G2_SHADES.format(g=self.gateway))
                if res.status_code == requests.codes.ok:
                    data = res.json()
                    self.shades_array = data['shadeData']
                    self.shadeIds_array = data['shadeIds']
                    for shade in self.shades_array:
                        name = base64.b64decode(shade['name']).decode()
                        room_name = self.rooms_array[self.roomIds_array.index(shade['roomId'])]['name']
                        room_name = room_name[0:ROOM_NAME_LIMIT]
                        shade['name'] = get_valid_node_name('%s - %s' % (room_name, name))
                        if 'positions' in shade:
                            pos = shade['positions']
                            # Convert positions to integer percentages & handle tilt
                            if 'posKind1' in pos:
                                if pos['posKind1'] == 1:
                                    if 'position1' in pos:
                                        shade['positions']['primary'] = self.toPercent(pos['position1'], G2_DIVR)
                                if pos['posKind1'] == 3:
                                    shade['positions']['primary'] = 0
                                    if 'position1' in pos:
                                        shade['positions']['tilt'] = self.toPercent(pos['position1'], G2_DIVR)
                            if 'position2' in pos:
                                shade['positions']['secondary'] = self.toPercent(pos['position2'], G2_DIVR)
                    LOGGER.info(f"shades = {self.shadeIds_array}")
                    
                res = self.get(URL_G2_SCENES.format(g=self.gateway))
                if res.status_code == requests.codes.ok:
                    data = res.json()
                    self.scenes_array = data['sceneData']
                    self.sceneIds_array = data['sceneIds']
                    for scene in self.scenes_array:
                        name = base64.b64decode(scene['name']).decode()
                        if scene['roomId'] == None:
                            room_name = "Multi"
                        else:
                            room_name = self.rooms_array[self.roomIds_array.index(scene['roomId'])]['name']
                            room_name = room_name[0:ROOM_NAME_LIMIT]
                        scene['name'] = get_valid_node_name('%s - %s' % (room_name, name))
                    LOGGER.info(f"scenes = {self.sceneIds_array}")

                self.no_update = False
                LOGGER.info(f"updateAllfromServerG2 = OK")
                return True
            else:
                self.no_update = False
                LOGGER.error(f"updateAllfromServerG2 = NO DATA")
                return False
        except:
            LOGGER.error('updateAllfromServerG2 = except')
            self.no_update = False
            return False
        
    def getHomeG2(self):
        """
        Get the home data from the gateway for Generation 2.
        """
        res = self.get(URL_G2_HUB.format(g=self.gateway))
        code = res.status_code
        if self.gateway_array:
            if code == requests.codes.ok:
                data = res.json()
                LOGGER.info("getHomeG2 gateway good %s, %s", self.gateway, self.gateway_array)
                return data
            else:
                LOGGER.error("getHomeG2 gateway NOT good %s, %s", self.gateway, self.gateway_array)
                if self.genCheck2():
                    LOGGER.error("getHomeG2 fixed %s, %s", self.gateway, self.gateway_array)
                else:
                    LOGGER.error("getHomeG2 still NOT fixed %s, %s", self.gateway, self.gateway_array)
        else:
            LOGGER.error("getHomeG2 self.gateway_array NONE")
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
        newpos = math.trunc((float(pos) / divr * 100.0) + 0.5)
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
        {'driver': 'ST', 'value': 1, 'uom': 2, 'name': "Controller Status"},
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
