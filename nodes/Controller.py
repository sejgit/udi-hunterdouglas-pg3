"""
udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/Polisy

(C) 2024 Stephen Jenkins

Controller class
"""

import udi_interface
import requests
import math
import base64
import time
import socket
import json

# Nodes
from nodes import *

"""
Some shortcuts for udi interface components

- LOGGER: to create log entries
- Custom: to access the custom data class
- ISY:    to communicate directly with the ISY (not commonly used)
"""
LOGGER = udi_interface.LOGGER
LOG_HANDLER = udi_interface.LOG_HANDLER
Custom = udi_interface.Custom
ISY = udi_interface.ISY
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

class Controller(udi_interface.Node):
    id = 'hdctrl'

    def __init__(self, polyglot, primary, address, name):
        """
        super
        self definitions
        data storage classes
        subscribes
        ready
        we exist!
        """
        super().__init__(polyglot, primary, address, name)

        self.poly = polyglot
        self.primary = primary
        self.address = address
        self.name = name
        self.n_queue = []
        self.last = 0.0
        self.no_update = False
        self.discovery = False
        self.gateway = URL_DEFAULT_GATEWAY
        self.gateway_array = []
        self.gateway_event = [{'evt': 'home', 'shades': [], 'scenes': []}]
        self.rooms_array = []
        self.roomIds_array = []
        self.shades_array = []
        self.shadeIds_array = []
        self.scenes_array = []
        self.sceneIds_array = []
        self.generation = 99 # start with unknown

        self.tiltCapable = [1, 2, 4, 5, 9, 10]
        self.tiltOnly90Capable = [1, 9]

        # Create data storage classes to hold specific data that we need
        # to interact with.  
        self.Parameters = Custom(polyglot, 'customparams')
        self.Notices = Custom(polyglot, 'notices')
        self.TypedParameters = Custom(polyglot, 'customtypedparams')
        self.TypedData = Custom(polyglot, 'customtypeddata')

        # Subscribe to various events from the Interface class.
        #
        # The START event is unique in that you can subscribe to 
        # the start event for each node you define.

        self.poly.subscribe(self.poly.START, self.start, address)
        self.poly.subscribe(self.poly.LOGLEVEL, self.handleLevelChange)
        self.poly.subscribe(self.poly.CUSTOMPARAMS, self.parameterHandler)
        self.poly.subscribe(self.poly.CUSTOMTYPEDPARAMS, self.typedParameterHandler)
        self.poly.subscribe(self.poly.CUSTOMTYPEDDATA, self.typedDataHandler)
        self.poly.subscribe(self.poly.POLL, self.poll)
        self.poly.subscribe(self.poly.STOP, self.stop)
        self.poly.subscribe(self.poly.DISCOVER, self.discover)
        self.poly.subscribe(self.poly.ADDNODEDONE, self.node_queue)

        # Tell the interface we have subscribed to all the events we need.
        # Once we call ready(), the interface will start publishing data.
        self.poly.ready()

        # Tell the interface we exist.  
        self.poly.addNode(self)

        '''
        node_queue() and wait_for_node_event() create a simple way to wait
        for a node to be created.  The nodeAdd() API call is asynchronous and
        will return before the node is fully created. Using this, we can wait
        until it is fully created before we try to use it.
        '''
    def node_queue(self, data):
        self.n_queue.append(data['address'])

    def wait_for_node_done(self):
        while len(self.n_queue) == 0:
            time.sleep(0.1)
        self.n_queue.pop()

    def start(self):
        self.Notices['hello'] = 'Start-up'

        self.last = 0.0
        # Send the profile files to the ISY if neccessary. The profile version
        # number will be checked and compared. If it has changed since the last
        # start, the new files will be sent.
        self.poly.updateProfile()

        # Send the default custom parameters documentation file to Polyglot
        # for display in the dashboard.
        self.poly.setCustomParamsDoc()

        # Initializing a heartbeat is an example of something you'd want
        # to do during start.  Note that it is not required to have a
        # heartbeat in your node server
        self.heartbeat(True)

        # Device discovery. Here you may query for your device(s) and 
        # their capabilities.  Also where you can create nodes that
        # represent the found device(s)
        self.gateway_sse = self.sseInit()
        # if self.checkParams():
        #     self.discover() # only do discovery if gateway change

    """
    Called via the CUSTOMPARAMS event. When the user enters or
    updates Custom Parameters via the dashboard. The full list of
    parameters will be sent to your node server via this event.

    Here we're loading them into our local storage so that we may
    use them as needed.

    New or changed parameters are marked so that you may trigger
    other actions when the user changes or adds a parameter.

    NOTE: Be carefull to not change parameters here. Changing
    parameters will result in a new event, causing an infinite loop.
    """
    def parameterHandler(self, params):
        self.Parameters.load(params)
        LOGGER.debug('Loading parameters now')
        if self.checkParams():
            self.discover() # only do discovery if gateway change
            self.gateway_sse = self.sseInit()

    """
    Called via the CUSTOMTYPEDPARAMS event. This event is sent When
    the Custom Typed Parameters are created.  See the checkParams()
    below.  Generally, this event can be ignored.

    Here we're re-load the parameters into our local storage.
    The local storage should be considered read-only while processing
    them here as changing them will cause the event to be sent again,
    creating an infinite loop.
    """
    def typedParameterHandler(self, params):
        self.TypedParameters.load(params)
        LOGGER.debug('Loading typed parameters now')
        LOGGER.debug(params)

    """
    Called via the CUSTOMTYPEDDATA event. This event is sent when
    the user enters or updates Custom Typed Parameters via the dashboard.
    'params' will be the full list of parameters entered by the user.

    Here we're loading them into our local storage so that we may
    use them as needed.  The local storage should be considered 
    read-only while processing them here as changing them will
    cause the event to be sent again, creating an infinite loop.
    """
    def typedDataHandler(self, params):
        self.TypedData.load(params)
        LOGGER.debug('Loading typed data now')
        LOGGER.debug(params)

    """
    Called via the LOGLEVEL event.
    """
    def handleLevelChange(self, level):
        LOGGER.info('New log level: {}'.format(level))

    def checkParams(self):
        """
        This is using custom Params for gatewayip
        """
        self.Notices.delete('gateway')
        gatewaycheck = self.gateway
        self.gateway = self.Parameters.gatewayip
        if self.gateway is None:
            self.gateway = URL_DEFAULT_GATEWAY
            LOGGER.warn('checkParams: gateway not defined in customParams, using {}'.format(URL_DEFAULT_GATEWAY))
            self.Notices['gateway'] = 'Please note using default gateway address'
            return (gatewaycheck != self.gateway)
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
            return (gatewaycheck != self.gateway)
        else:
            LOGGER.warn(f"checkParams: no gateway found in {self.gateway_array}")
            self.Notices['gateway'] = 'Please note no primary gateway found in gatewayip'
            return False
                                
    def goodip(self):
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
        for ip in self.gateway_array:
            res = self.get(URL_G2_HUB.format(g=ip))
            if res.status_code == requests.codes.ok:
                LOGGER.info(f"{ip} is PowerView 2")
                self.gateway = ip
                self.generation = 2
                return True
        return False
            
    """
    Called via the POLL event.  The POLL event is triggerd at
    the intervals specified in the node server configuration. There
    are two separate poll events, a long poll and a short poll. Which
    one is indicated by the flag.  flag will hold the poll type either
    'longPoll' or 'shortPoll'.

    Use this if you want your node server to do something at fixed
    intervals.
    """
    def poll(self, flag):
        # pause updates when in discovery
        if self.discovery == True:
            return
        if 'longPoll' in flag:
            LOGGER.debug('longPoll re-parse updateallfromserver (controller)')
            self.updateAllFromServer()
            try:
                event = list(filter(lambda events: events['evt'] == 'homedoc-updated', self.gateway_event))
                if event:
                    event = event[0]
                    LOGGER.debug('longPoll event - no action {}'.format(event))
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

                if self.Notices['hello']:
                    self.Notices.delete('hello')
            except:
                LOGGER.error("LongPoll event error")
            self.heartbeat()
            LOGGER.info("event(total) = {}".format(self.gateway_event))
        else:
            LOGGER.debug('shortPoll check for events (controller)')
            try:
                if self.gateway_sse:
                    x = self.gateway_sse
                    y = next(x)
                    try:
                        yy = json.loads(y)
                    except:
                        try:
                            yy = json.loads(y + next(x))
                        except:
                            yy = {}
                    self.gateway_event.append(yy)
                    LOGGER.info(f"new event = {yy}")
            except:
                pass
                # LOGGER.debug('shortPoll nothing to do')

    def sseInit(self):
        """
        connect and pull from the gateway stream of events ONLY FOR G3
        """
        self.gateway_event = [{'evt': 'home', 'shades': [], 'scenes': []}]

        if self.generation == 3:
            url = URL_EVENTS.format(g=self.gateway)
            try:
               sse = requests.get(url, headers={"Accept": "application/x-ldjson"}, stream=True)
               x = (s.rstrip() for s in sse)
               y = str("raw = {}".format(next(x)))
               LOGGER.info(y)
            except:
                x = False
        else:
            x = False
        return x

    def query(self, command = None):
        """
        The query method will be called when the ISY attempts to query the
        status of the node directly.  You can do one of two things here.
        You can send the values currently held by Polyglot back to the
        ISY by calling reportDriver() or you can actually query the 
        device represented by the node and report back the current 
        status.
        """
        if self.updateAllFromServer():
            nodes = self.poly.getNodes()
            for node in nodes:
                nodes[node].reportDrivers()

    def updateProfile(self,command):
        LOGGER.info('update profile')
        st = self.poly.updateProfile()
        return st

    def discover(self, command = None):
        """
        Do shade and scene discovery here. Called from controller start method
        and from DISCOVER command received from ISY
        """
        if self.discovery:
            LOGGER.info('Discover already running.')
            return

        self.discovery = True
        LOGGER.info("In Discovery...")

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

                shTxt = 'shade{}'.format(shadeId)
                nodes_new.append(shTxt)
                capabilities = int(shade['capabilities'])
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
                
                scTxt = 'scene{}'.format(sceneId)
                nodes_new.append(scTxt)
                if scTxt not in nodes:
                    self.poly.addNode(Scene(self.poly, \
                                            self.address, \
                                            scTxt, \
                                            scene["name"], \
                                            sceneId))
                    self.wait_for_node_done()

        # remove nodes which do not exist in gateway
        nodes = self.poly.getNodes()
        nodes_get = {key: nodes[key] for key in nodes if key != self.id}
        LOGGER.info(f"old nodes = {nodes_old}")
        LOGGER.info(f"new nodes = {nodes_new}")
        LOGGER.info(f"pre-delete nodes = {nodes_get}")
        for node in nodes_get:
            if (node not in nodes_new):
                LOGGER.info(f"need to delete node {node}")
                self.poly.delNode(node)

        self.discovery = False
        LOGGER.info('Discovery complete.')

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
        LOGGER.info('NodeServer stopped.')

    def heartbeat(self,init=False):
        """
        This is a heartbeat function.  It uses the
        long poll interval to alternately send a ON and OFF command back to
        the ISY.  Programs on the ISY can then monitor this and take action
        when the heartbeat fails to update.
        """
        LOGGER.debug('heartbeat: init={}'.format(init))
        if init is not False:
            self.hb = init
        LOGGER.debug('heartbeat: hb={}'.format(self.hb))
        if self.hb == 0:
            self.reportCmd("DON",2)
            self.hb = 1
        else:
            self.reportCmd("DOF",2)
            self.hb = 0

    def removeNoticesAll(self, command = None):
        LOGGER.info('remove_notices_all: notices={}'.format(self.Notices))
        # Remove all existing notices
        self.Notices.clear()

    def updateAllFromServer(self):
        success = True
        if time.perf_counter() > (self.last + 3.0):
            self.no_update = True
            self.last = time.perf_counter()
            if self.generation == 3:
                success = self.updateAllFromServerG3(self.getHomeG3())
            elif self.generation == 2:
                success = self.updateAllFromServerG2(self.getHomeG2())
            else:
                success = False
        self.no_update = False
        return success
        
    def updateAllFromServerG3(self, data):
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
                        sh['name'] = '%s - %s' % (room_name, name)
                        LOGGER.debug(sh['name'])
                        if 'positions' in sh:
                            # Convert positions to integer percentages
                            sh['positions']['primary'] = self.toPercent(sh['positions']['primary'])
                            sh['positions']['secondary'] = self.toPercent(sh['positions']['secondary'])
                            sh['positions']['tilt'] = self.toPercent(sh['positions']['tilt'])
                            sh['positions']['velocity'] = self.toPercent(sh['positions']['velocity'])
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
                    room_name = self.rooms_array[self.roomIds_array.index(sc['room_Id'])]['name']
                    room_name = room_name[0:ROOM_NAME_LIMIT]
                    sc['name'] = '%s - %s' % (room_name, name)
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
        
    def updateAllFromServerG2(self, data):
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
                        shade['name'] = '%s - %s' % (room_name, name)
                        if 'positions' in shade:
                            pos = shade['positions']
                            # Convert positions to integer percentages & handle tilt
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
                        room_name = self.rooms_array[self.roomIds_array.index(scene['roomId'])]['name']
                        room_name = room_name[0:ROOM_NAME_LIMIT]
                        scene['name'] = '%s - %s' % (room_name, name)
                    LOGGER.info(f" {self.sceneIds_array}")

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
        
    def getHomeG3(self):
        res = self.get(URL_HOME.format(g=self.gateway))
        code = res.status_code
        data = res.json()
        if self.gateway_array:
            if code == requests.codes.ok:
                LOGGER.info("getHomeG3 gateway good %s, %s", self.gateway, self.gateway_array)
                return data
            else:
                LOGGER.info("getHomeG3 gateway NOT good %s, %s", self.gateway, self.gateway_array)
                if self.genCheck3():
                    LOGGER.info("getHomeG3 fixed %s, %s", self.gateway, self.gateway_array)
                else:
                    LOGGER.info("getHomeG3 still NOT fixed %s, %s", self.gateway, self.gateway_array)
        return None

    def getHomeG2(self):
        res = self.get(URL_G2_HUB.format(g=self.gateway))
        code = res.status_code
        data = res.json()
        if self.gateway_array:
            if code == requests.codes.ok:
                LOGGER.info("getHomeG2 gateway good %s, %s", self.gateway, self.gateway_array)
                return data
            else:
                LOGGER.info("getHomeG2 gateway NOT good %s, %s", self.gateway, self.gateway_array)
                if self.genCheck2():
                    LOGGER.info("getHomeG2 fixed %s, %s", self.gateway, self.gateway_array)
                else:
                    LOGGER.info("getHomeG2 still NOT fixed %s, %s", self.gateway, self.gateway_array)
        return None
    
    def get(self, url):
        res = None
        try:
            res = requests.get(url, headers={'accept': 'application/json'})
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"Error {e} fetching {url}")
            res = requests.Response()
            res.status_code = 300
            res.raw = {"errMsg":"Error fetching from gateway, check configuration"}
            self.Notices['badfetch'] = "Error fetching from gateway"
            return res
        if res.status_code == 400:
            LOGGER.info(f"Check if not primary {url}: {res.status_code}")
            self.Notices['notPrimary'] = "Multi-Gateway environment - this is not primary"
            return res
        if res.status_code == 404:
            LOGGER.info(f"Gateway wrong {url}: {res.status_code}")
            return res
        if res.status_code == 503:
            LOGGER.info(f"HomeDoc not set-up {url}: {res.status_code}")
            self.Notices['HomeDoc'] = "PowerView Set-up not Complete See TroubleShooting Guide"
            return res
        elif res.status_code != requests.codes.ok:
            LOGGER.warn(f"Unexpected response fetching {url}: {res.status_code}")
            return res
        else:
            LOGGER.debug(f"Get from '{url}' returned {res.status_code}, response body '{res.text}'")
        self.Notices.delete('badfetch')
        self.Notices.delete('notPrimary')
        self.Notices.delete('HomeDoc')
        return res

    def toPercent(self, pos, divr=1.0):
        newpos = math.trunc((float(pos) / divr * 100.0) + 0.5)
        LOGGER.debug(f"toPercent: pos={pos}, becomes {newpos}")
        return newpos

    def put(self, url, data=None):
        res = None
        try:
            if data:
                res = requests.put(url, json=data, headers={'accept': 'application/json'})
            else:
                res = requests.put(url, headers={'accept': 'application/json'})

        except requests.exceptions.RequestException as e:
            LOGGER.error(f"Error {e} in put {url} with data {data}:", exc_info=True)
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
    ]
    
    # Commands that this node can handle.  Should match the
    # 'accepts' section of the nodedef file.
    commands = {
        'QUERY': query,
        'DISCOVER': discover,
        'UPDATE_PROFILE': updateProfile,
        'REMOVE_NOTICES_ALL': removeNoticesAll,
    }
