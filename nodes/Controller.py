"""
udi-HunterDouglas-pg3 NodeServer/Plugin for EISY/PolISY

(C) 2024 Stephen Jenkins
"""

"""
Get the polyinterface objects we need. 
"""
import udi_interface
import requests
import math
import base64

# powerview3 class
from nodes import PowerViewGen3

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

# IF you want a different log format than the current default
LOG_HANDLER.set_log_format('%(asctime)s %(threadName)-10s %(name)-18s %(levelname)-8s %(module)s:%(funcName)s: %(message)s')

class Controller(udi_interface.Node):
    """
    The Node class represents a node on the ISY. The first node started and
    that is is used for interaction with the node server is typically called
    a 'Controller' node. If this node has the address 'controller', Polyglot
    will automatically populate the 'ST' driver of this node with the node
    server's on-line/off-line status.

    This node will also typically handle discovery & creation of other nodes
    and deal with the user configurable options of the node server.

    Class Variables:
      self.name: String name of the node
      self.address: String Address of Node, must be less than 14 characters
                    (ISY limitation)
      self.primary: String Address of Node's parent, must be less than 14
                    characters (ISY limitation)
      self.poly: Interface class object.  Provides access to the interface API.

    Class Methods
      query(): Queries and reports ALL drivers for ALL nodes to the ISY.
      getDriver('ST'): gets the current value from Polyglot for driver 'ST'
        returns a STRING, cast as needed
      setDriver('ST', value, report, force, uom): Updates the driver with
        the value (and possibly a new UOM)
      reportDriver('ST', force): Send the driver value to the ISY, normally
        it will only send if the value has changed, force will always send
      reportDrivers(): Send all driver values to the ISY
      status()
    """
    def __init__(self, polyglot, primary, address, name):
        """
        Optional.
        Super runs all the parent class necessities. You do NOT have
        to override the __init__ method, but if you do, you MUST call super.

        In most cases, you will want to do this for the controller node.
        """
        super(Controller, self).__init__(polyglot, primary, address, name)

        self.poly = polyglot
        self.parent = primary
        self.address = address
        self.name = name

        self.hb = 0
        self.gateway = 'powerview-g3.local'

        # Create data storage classes to hold specific data that we need
        # to interact with.  
        self.Parameters = Custom(polyglot, 'customparams')
        self.Notices = Custom(polyglot, 'notices')
        self.TypedParameters = Custom(polyglot, 'customtypedparams')
        self.TypedData = Custom(polyglot, 'customtypeddata')

        # Subscribe to various events from the Interface class.  This is
        # how you will get information from Polyglog.  See the API
        # documentation for the full list of events you can subscribe to.
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
        """
        The Polyglot v3 Interface will publish an event to let you know you
        can start your integration. (see the START event subscribed to above)

        This is where you do your initialization / device setup.
        Polyglot v3 Interface startup done.

        Here is where you start your integration. I.E. if you need to 
        initiate communication with a device, do so here.
        """

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
        self.heartbeat(False)

        # Device discovery. Here you may query for your device(s) and 
        # their capabilities.  Also where you can create nodes that
        # represent the found device(s)
        self.discover()

        # Here you may want to send updated values to the ISY rather
        # than wait for a poll interval.  The user will get more 
        # immediate feedback that the node server is running

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
        self.check_params()

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
            LOGGER.debug('longPoll (controller)')
            self.heartbeat()
        else:
            LOGGER.debug('shortPoll (controller)')

    def query(self,command=None):
        """
        The query method will be called when the ISY attempts to query the
        status of the node directly.  You can do one of two things here.
        You can send the values currently held by Polyglot back to the
        ISY by calling reportDriver() or you can actually query the 
        device represented by the node and report back the current 
        status.
        """
        nodes = self.poly.getNodes()
        for node in nodes:
            nodes[node].reportDrivers()

    def discover(self, *args, **kwargs):
        """
        Do discovery here. Does not have to be called discovery. Called from
        example controller start method and from DISCOVER command received
        from ISY as an example.
        """
        global powerview3
        self.powerview3 = PowerViewGen3()
        
        # self.poly.addNode(myNode(self.poly, self.address, 'nodeaddress', 'Test Node Name'))

        self.shadeIds = None
        self.shadeIds = self.powerview3.shadeIds(self.gateway)
        for shadeId in self.shadeIds:
            shade = self.powerview3.shade(self.gateway, shadeId)
            self.poly.addNode(Shade(self.poly, self.address, 'shade{}'.format(shadeId), shade["name"], shade))

        self.scenes = None
        self.scenes = self.powerview3.scenes(self.gateway)
        for scene in self.scenes:
            self.poly.addNode(Scene(self.poly, self.address, "scene{}".format(scene["id"]), scene["name"],scene))

    def delete(self):
        """
        This is call3ed by Polyglot upon deletion of the NodeServer. If the
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
        LOGGER.debug('NodeServer stopped.')

    """
    This is a heartbeat function.  It uses the
    long poll intervale to alternately send a ON and OFF command back to
    the ISY.  Programs on the ISY can then monitor this and take action
    when the heartbeat fails to update.
    """
    def heartbeat(self,init=False):
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
        self.Notices.clear()
        self.Notices['hello'] = 'Start-up'

        default_gateway = "powerview-g3.local"
        self.gateway = self.Parameters.gatewayip
        if self.gateway is None:
            self.gateway = default_gateway
            LOGGER.warn('check_params: gateway not defined in customParams, using {}'.format(default_gateway))

        # Add a notice if they need to change the user/password from the default.
        if self.gateway == default_gateway:
            self.Notices['gateway'] = 'Please note using default gateway address'

    def remove_notices_all(self,command):
        LOGGER.info('remove_notices_all: notices={}'.format(self.Notices))
        # Remove all existing notices
        self.Notices.clear()

    id = 'hdctrl'

    # Commands that this node can handle.  Should match the
    # 'accepts' section of the nodedef file.
    commands = {
        'QUERY': query,
        'DISCOVER': discover,
        'REMOVE_NOTICES_ALL': remove_notices_all,
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

