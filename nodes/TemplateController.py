

"""
Get the polyinterface objects we need.  Currently Polyglot Cloud uses
a different Python module which doesn't have the new LOG_HANDLER functionality
"""
from udi_interface import Custom,Node,LOG_HANDLER,LOGGER
import logging

# My Template Node
from nodes import TemplateNode

# IF you want a different log format than the current default
LOG_HANDLER.set_log_format('%(asctime)s %(threadName)-10s %(name)-18s %(levelname)-8s %(module)s:%(funcName)s: %(message)s')

class TemplateController(Node):
    """
    The Node class represents a node on the ISY. The first node started and that is 
    is used to for interaction with the node server is typically called a 'Controller'
    node. If this node has the address 'controller', Polyglot will automatically populate
    the 'ST' driver of this node with the node server's on-line/off-line status.

    This node will also typically handle discovery & creation of other nodes and deal
    with the user configurable options of the node server.

    Class Variables:
    self.name: String name of the node
    self.address: String Address of Node, must be less than 14 characters (ISY limitation)
    self.primary: String Address of Node's parent, must be less than 14 characters (ISY limitation)
    self.poly: Interface class object.  Provides access to the interface API.

    Class Methods
    query(): Queries and reports ALL drivers for ALL nodes to the ISY.
    getDriver('ST'): gets the current value from Polyglot for driver 'ST' returns a STRING, cast as needed
    setDriver('ST', value, report, force, uom): Updates the driver with the value (and possibly a new UOM)
    reportDriver('ST', force): Send the driver value to the ISY, normally it will only send if the value has changed, force will always send
    reportDrivers(): Send all driver values to the ISY
    status()
    delNode(): Delete the node from the ISY and Polyglot database
    """
    def __init__(self, polyglot, primary, address, name):
        """
        Optional.
        Super runs all the parent class necessities. You do NOT have
        to override the __init__ method, but if you do, you MUST call super.
        """
        super(TemplateController, self).__init__(polyglot, primary, address, name)
        self.poly = polyglot
        self.name = 'Template Controller'
        self.hb = 0

        # Create data storage classes to hold specific data that we need
        # to interact with.  
        self.Parameters = Custom(polyglot, 'customparams')
        self.Notices = Custom(polyglot, 'notices')
        self.TypedParameters = Custom(polyglot, 'customtypedparams')

        self.poly.onConfig(self.configHandler) # register to get config data sent by Polyglot
        self.poly.onCustomParams(self.parameterHandler) # register to get parameter info sent by Polyglot
        self.poly.onCustomTypedParams(self.typedParameterHandler) # register to get typed parameter info sent by Polyglot
        self.poly.onStart(address, self.start) # register a function to run when the node is added
        self.poly.onPoll(self.poll) # register to get short and long poll events

        # Tell the interface we exist.  
        self.poly.addNode(self)



    def start(self):
        """
        Optional.
        Polyglot v3 Interface startup done. Here is where you start your integration.
        This is called via the onStart callback configured above, once the node has
        been added to the interface.

        In this example we call various methods that deal with initializing the
        node server. This is where you should start. No need to Super this method,
        the parent version does nothing.
        """
        self.check_params()

        # Send the profile files to the ISY if neccessary. The profile version
        # number will be checked and compared. If it has changed since the last
        # start, the new files will be sent.
        self.poly.updateProfile()

        # Send the default custom parameters documentation file to Polyglot
        # for display in the dashboard.
        self.poly.setCustomParamsDoc()

        self.heartbeat(0)
        self.discover()

        # Here you may want to send updated values to the ISY rather
        # than wait for a poll interval.  The user will get more 
        # immediate feedback that the node server is running

    """
    Called via the onConfig event.  When the interface receives a
    configuration structure from Polyglot, it will send that config
    to your node server via this callback.

    The config structure does contain the list of nodes & last
    driver values stored in the database.  These can be accessed
    here to update your node server with the previous state.
    """
    def configHandler(self, config):
        pass

    """
    Called via the onCustomParams event. When the user enters or
    updates Custom Parameters via the dashboard. The full list of
    parameters will be sent to your node server via this callback.

    Here we're loading them into our local storage so that we may
    use them as needed.

    New or changed parameters are marked so that you may trigger
    other actions when the user changes or adds a parameter.
    """
    def parameterHandler(self, params):
        self.Parameters.load(params)

    """
    Called via the onCustomParams event. When the user enters or
    updates Custom Parameters via the dashboard. The full list of
    parameters will be sent to your node server via this callback.

    Here we're loading them into our local storage so that we may
    use them as needed.
    """
    def typedParameterHandler(self, params):
        self.TypedParameters.load(params)

    """
    Called via the onPoll event.  The onPoll event is triggerd at
    the intervals specified in the node server configuration. There
    are two separate poll events, a long poll and a short poll. Which
    one is indicated by the flag.  flag==True indicates a long poll 
    event.

    Use this if you want your node server to do something at fixed
    intervals.
    """
    def poll(self, flag):
        if flag:
            LOGGER.debug('longPoll (controller)')
            self.heartbeat()
        else:
            LOGGER.debug('shortPoll (controller)')

    def query(self,command=None):
        """
        Optional.
        By default a query to the control node reports the FULL driver set for ALL
        nodes back to ISY. If you override this method you will need to Super or
        issue a reportDrivers() to each node manually.
        """
        self.check_params()
        nodes = self.poly.getNodes()
        for node in nodes:
            nodes[node].reportDrivers()

    def discover(self, *args, **kwargs):
        """
        Example
        Do discovery here. Does not have to be called discovery. Called from example
        controller start method and from DISCOVER command recieved from ISY as an exmaple.
        """
        self.poly.addNode(TemplateNode(self.poly, self.address, 'templateaddr', 'Template Node Name'))

    def delete(self):
        """
        Example
        This is sent by Polyglot upon deletion of the NodeServer. If the process is
        co-resident and controlled by Polyglot, it will be terminiated within 5 seconds
        of receiving this message.
        """
        LOGGER.info('Oh God I\'m being deleted. Nooooooooooooooooooooooooooooooooooooooooo.')

    def stop(self):
        LOGGER.debug('NodeServer stopped.')


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

    def set_module_logs(self,level):
        logging.getLogger('urllib3').setLevel(level)

    def check_params(self):
        """
        This is an example if using custom Params for user and password and an example with a Dictionary
        """
        self.Notices.clear()
        self.Notices['hello'] = 'Hey there, my IP is {}'.format(self.poly.network_interface['addr'])
        self.Notices['hello2'] = 'Hello Friends!'
        default_user = "YourUserName"
        default_password = "YourPassword"

        #self.user = self.getCustomParam('user')
        self.user = self.Parameters.user
        if self.user is None:
            self.user = default_user
            LOGGER.error('check_params: user not defined in customParams, please add it.  Using {}'.format(self.user))
            #self.addCustomParam({'user': self.user})
            self.Parameters.user = self.user

        #self.password = self.getCustomParam('password')
        self.password = self.Parameters.password
        if self.password is None:
            self.password = default_password
            LOGGER.error('check_params: password not defined in customParams, please add it.  Using {}'.format(self.password))
            #self.addCustomParam({'password': self.password})
            self.Parameters.password = self.password

        # Always overwrite this, it's just an example...
        self.Parameters.type = "TheType"
        self.Parameters.host = "host_or_IP"
        self.Parameters.port = "port_number"

        # Add a notice if they need to change the user/password from the default.
        if self.user == default_user or self.password == default_password:
            self.Notices['auth'] = 'Please set proper user and password in configuration page'
            self.Notices['test'] = 'This is only a test'

        # Typed Parameters allow for more complex parameter entries.
        #self.poly.save_typed_params(
        self.TypedParameters.load( [
                {
                    'name': 'item',
                    'title': 'Item',
                    'desc': 'Description of Item',
                    'isList': False,
                    'params': [
                        {
                            'name': 'id',
                            'title': 'The Item ID',
                            'isRequired': True,
                        },
                        {
                            'name': 'title',
                            'title': 'The Item Title',
                            'defaultValue': 'The Default Title',
                            'isRequired': True,
                        },
                        {
                            'name': 'extra',
                            'title': 'The Item Extra Info',
                            'isRequired': False,
                        }
                    ]
                },
                {
                    'name': 'itemlist',
                    'title': 'Item List',
                    'desc': 'Description of Item List',
                    'isList': True,
                    'params': [
                        {
                            'name': 'id',
                            'title': 'The Item ID',
                            'isRequired': True,
                        },
                        {
                            'name': 'title',
                            'title': 'The Item Title',
                            'defaultValue': 'The Default Title',
                            'isRequired': True,
                        },
                        {
                            'name': 'names',
                            'title': 'The Item Names',
                            'isRequired': False,
                            'isList': True,
                            'defaultValue': ['somename']
                        },
                        {
                            'name': 'extra',
                            'title': 'The Item Extra Info',
                            'isRequired': False,
                            'isList': True,
                        }
                    ]
                },
            ], True)

    def remove_notice_test(self,command):
        LOGGER.info('remove_notice_test: notices={}'.format(self.Notices))
        # Remove all existing notices
        self.Notices.delete('test')
        #self.removeNotice('test')

    def remove_notices_all(self,command):
        LOGGER.info('remove_notices_all: notices={}'.format(self.Notices))
        # Remove all existing notices
        self.Notices.clear()

    """
    Optional.
    Since the controller is a node in ISY, it will actual show up as a node.
    So it needs to know the drivers and what id it will use. The controller should
    report the node server status and have any commands that are needed to control
    operation of the node server.

    Typically, node servers will use the 'ST' driver to report the node server status
    and it a best pactice to do this unless you have a very good reason not to.

    The id must match the nodeDef id="controller" in the nodedefs.xml
    """
    id = 'controller'
    commands = {
        'QUERY': query,
        'DISCOVER': discover,
        'REMOVE_NOTICES_ALL': remove_notices_all,
        'REMOVE_NOTICE_TEST': remove_notice_test,
    }
    drivers = [
        {'driver': 'ST', 'value': 1, 'uom': 2},
    ]
