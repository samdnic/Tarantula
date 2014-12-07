import os
import cherrypy

import xml.etree.ElementTree as XMLParser

from SQLEngine import SAEnginePlugin, SATool

import EventProcessorBase

from EventDataWebService import EventDataWebService, EVENTDATASERVICE_CONF
from PluginDataWebService import PluginDataWebService, PLUGINDATASERVICE_CONF
from ScheduleDataWebService import ScheduleDataWebService, SCHEDULEDATASERVICE_CONF

MOUNT_LOCATION_SUFFIX = '/api/v1.0'


if __name__ == '__main__':
    # Load configuration data
    tree = XMLParser.parse('config/WebService.xml')
    configroot = tree.getroot()
    
    mount_location = os.path.join(configroot.find('MountStem').text, MOUNT_LOCATION_SUFFIX)
    
    
    EventProcessorBase.setup_event_processors(configroot.find('ProcessorConfigFiles').text)
    
    cherrypy.server.socket_port = int(configroot.find('Port').text)
    
    # Configure the database
    SAEnginePlugin(cherrypy.engine, 'sqlite:///{0}'.format(configroot.find('Database').text)).subscribe()
    cherrypy.tools.db = SATool()
    
    # Mount all the web services and directories
    cherrypy.tree.mount(EventDataWebService(), '{0}/events'.format(mount_location), EVENTDATASERVICE_CONF)
    cherrypy.tree.mount(PluginDataWebService(), '{0}/plugins'.format(mount_location), PLUGINDATASERVICE_CONF)
    cherrypy.tree.mount(ScheduleDataWebService(), '{0}/schedule'.format(mount_location), SCHEDULEDATASERVICE_CONF)
    
    # Run the web host engine
    cherrypy.engine.start()
    cherrypy.engine.block()