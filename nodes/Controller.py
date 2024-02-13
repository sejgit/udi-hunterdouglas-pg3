"""
udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/PolISY

(C) 2024 Stephen Jenkins
"""

import udi_interface
import requests
import math
import base64
import time
import socket
import json

# Nodes
from nodes import Scene
from nodes import Shade

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


"""
HunterDouglas PowerViewGen3 url's
"""
URL_DEFAULT_GATEWAY = 'powerview-g3.local'
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
HunterDouglas PowerViewGen2 url's
"""
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
        super(Controller, self).__init__(polyglot, primary, address, name)

        self.poly = polyglot
        self.parent = primary
        self.address = address
        self.name = name
        self.last = 0.0
        self.no_update = False
        self.gateway = URL_DEFAULT_GATEWAY
        self.gateway_array = []
        self.gateway_event = [{'evt': 'home', 'shades': [], 'scenes': []}]
        self.rooms_array = []
        self.roomIds_array = []
        self.shades_array = []
        self.shadeIds_array = []
        self.scenes_array = []
        self.sceneIds_array = []

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

        # Tell the interface we have subscribed to all the events we need.
        # Once we call ready(), the interface will start publishing data.
        self.poly.ready()

        # Tell the interface we exist.  
        self.poly.addNode(self)

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
        if self.check_params():
            self.discover() # only do discovery if gateway change

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
        if self.check_params():
            self.gateway_sse = self.sseInit()
            self.discover() # only do discovery if gateway change

    """
    Called via the CUSTOMTYPEDPARAMS event. This event is sent When
    the Custom Typed Parameters are created.  See the check_params()
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
        if 'longPoll' in flag:
            LOGGER.debug('longPoll re-parse updateallfromserver (controller)')
            self.updateAllFromServer()

            event = list(filter(lambda events: events['evt'] == 'home', self.gateway_event))
            if event:
                event = event[0]
                self.gateway_event[self.gateway_event.index(event)]['shades'] = self.shadeIds_array
                self.gateway_event[self.gateway_event.index(event)]['scenes'] = self.sceneIds_array
                LOGGER.debug('longpoll trigger nodes {}'.format(self.gateway_event))
            else:
                self.gateway_event.append({'evt': 'home', 'shades': [], 'scenes': []})
                LOGGER.debug('long poll reset {}'.format(self.gateway_event))

            if self.Notices['hello']:
                self.Notices.delete('hello')
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
                        yy = json.loads(y + next(x))
                    self.gateway_event.append(yy)
                    LOGGER.info(f"new event = {yy}")
            except:
                LOGGER.debug('shortPoll nothing to do')

    def sseInit(self):
        """
        connect and pull from the gateway stream of events
        """
        url = URL_EVENTS.format(g=self.gateway)
        try:
           sse = requests.get(url, headers={"Accept": "application/x-ldjson"}, stream=True)
           x = (s.rstrip() for s in sse)
           y = str("raw = {}".format(next(x)))
           LOGGER.info(y)
        except:
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
        if self.updateAllFromServer():
            for shade in self.shades_array:
                self.poly.addNode(Shade(self.poly, \
                                        self.address, \
                                        'shade{}'.format(shade['shadeId']), \
                                        shade["name"], \
                                        shade['shadeId']))
            for scene in self.scenes_array:
                self.poly.addNode(Scene(self.poly, \
                                        self.address, \
                                        "scene{}".format(scene["_id"]), \
                                        scene["name"], \
                                        scene["_id"]))

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

    def check_params(self):
        """
        This is using custom Params for gateway IP
        """
        gatewaycheck = self.gateway
        self.gateway = self.Parameters.gatewayip
        if self.gateway is None:
            self.gateway = URL_DEFAULT_GATEWAY
            LOGGER.warn('check_params: gateway not defined in customParams, using {}'.format(URL_DEFAULT_GATEWAY))
            self.Notices['gateway'] = 'Please note using default gateway address'
        else:
            self.Notices.delete('gateway')
            try:
                socket.inet_aton(self.gateway)
                LOGGER.info("good ip")
            except socket.error:
                try:
                    if type(eval(self.gateway)) == list:
                        self.gateway_array = eval(self.gateway)
                        self.gateway = self.gateway_array[0]
                        LOGGER.info('we have a list %s', self.gateway_array)
                        LOGGER.info("self.gateway = %s", self.gateway)
                    else:
                        LOGGER.error('we have a bad gateway %s', self.gateway)
                        self.Notices['gateway'] = 'Please note bad gateway address check customParams'
                except:
                    LOGGER.error('we also have a bad gateway %s', self.gateway)
                    self.Notices['gateway'] = 'Please note bad gateway address check customParams'
        if gatewaycheck != self.gateway:
            return True # gateway changed
        else:
            return False # no gateway change
                    
    def removeNoticesAll(self, command = None):
        LOGGER.info('remove_notices_all: notices={}'.format(self.Notices))
        # Remove all existing notices
        self.Notices.clear()

    def updateAllFromServer(self):
        if time.perf_counter() > (self.last + 3.0):
            # if True:
            self.no_update = True
            self.last = time.perf_counter()
            data = self.getHome()
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
                        sc['name'] = '%s - %s' % (room_name, name)
                        LOGGER.debug('Update scenes-1')

                    LOGGER.info(f"scenes = {self.sceneIds_array}")
                    self.home = data
                    self.no_update = False
                    return True
                else:
                    self.no_update = False
                    return False
            except:
                LOGGER.error('Update error')
                self.no_update = False
                return False
        self.no_update = False
        return True

    def getHome(self):
        code, data = self.get(URL_HOME.format(g=self.gateway))
        if self.gateway_array:
            if code != 400:
                LOGGER.info("array good %s, %s", self.gateway, self.gateway_array)
            else:
                current = self.gateway
                gateways = self.gateway_array
                gateways.remove(current)

                for new in gateways:
                    if not gateways:
                        LOGGER.error("exit get_array early")
                        return {}
                    else:
                        code, data = self.get(URL_HOME.format(g=new))
                        if code == requests.codes.ok:
                            LOGGER.info("found primpary gateway %s", new)
                            self.gateway = new
                            self.gateway_sse = self.sseInit()
                            return data
                        elif code != 400:
                            return {}
                        else: # code is 400
                            LOGGER.info("search for primary, move on to next %s, %s", new, gateways)

        return data

    def get(self, url):
        res = None
        try:
            res = requests.get(url, headers={'accept': 'application/json'})
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"Error {e} fetching {url}")
            self.Notices['badfetch'] = 'Error fetching from gateway, check configuration.'
            return 300, {}
        if res.status_code == 400:
            LOGGER.info(f"Check if not primary {url}: {res.status_code}")
            return 400, {}
        elif res.status_code != requests.codes.ok:
            LOGGER.warn(f"Unexpected response fetching {url}: {res.status_code}")
            return res.status_code, {}
        else:
            LOGGER.debug(f"Get from '{url}' returned {res.status_code}, response body '{res.text}'")
        self.Notices.delete('badfetch')
        return 200, res.json()

    def activateScene(self, sceneId):
        activateSceneUrl = URL_SCENES_ACTIVATE.format(g=self.gateway, id=sceneId)
        self.put(activateSceneUrl)

    def jogShade(self, shadeId):
        shadeUrl = URL_SHADES_MOTION.format(g=self.gateway, id=shadeId)
        body = {
            "motion": "jog"
        }
        self.put(shadeUrl, data=body)

    def stopShade(self, shadeId):
        shadeUrl = URL_SHADES_STOP.format(g=self.gateway, id=shadeId)
        self.put(shadeUrl)

    def setShadePosition(self, shadeId, pos):
        positions = {}

        if pos.get('primary') in range(0, 101):
            positions["primary"] = float(pos.get('primary', '0')) / 100.0

        if pos.get('secondary') in range(0, 101):
            positions["secondary"] = float(pos.get('secondary', '0')) / 100.0

        if pos.get('tilt') in range(0, 101):
            positions["tilt"] = float(pos.get('tilt', '0')) / 100.0

        if pos.get('velocity') in range(0, 101):
            positions["velocity"] = float(pos.get('velocity', '0')) / 100.0

        shade_url = URL_SHADES_POSITIONS.format(g=self.gateway, id=shadeId)
        pos = {'positions': positions}
        self.put(shade_url, pos)
        return True

    def toPercent(self, pos, divr=1.0):
        LOGGER.debug(f"toPercent: pos={pos}, becomes {math.trunc((float(pos) / divr * 100.0) + 0.5)}")
        return math.trunc((float(pos) / divr * 100.0) + 0.5)

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
                LOGGER.debug(f"Get from '{url}' returned {res.status_code}, response body '{res.text}'")
            return False

        if res and res.status_code != requests.codes.ok:
            LOGGER.error('Unexpected response in put %s: %s' % (url, str(res.status_code)))
            LOGGER.debug(f"Get from '{url}' returned {res.status_code}, response body '{res.text}'")
            return False

        response = res.json()
        return response

    # Commands that this node can handle.  Should match the
    # 'accepts' section of the nodedef file.
    commands = {
        'QUERY': query,
        'DISCOVER': discover,
        'UPDATE_PROFILE': updateProfile,
        'REMOVE_NOTICES_ALL': removeNoticesAll,
    }

    # Status that this node has. Should match the 'sts' section
    # of the nodedef file.
    drivers = [
        {'driver': 'ST', 'value': 1, 'uom': 2},
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

