import cherrypy

from SQLEngine import SAEnginePlugin, SATool

import EventProcessorBase

from EventDataWebService import EventDataWebService, EVENTDATASERVICE_CONF
from PluginDataWebService import PluginDataWebService, PLUGINDATASERVICE_CONF

MOUNT_LOCATION = '/api/v1.0'


if __name__ == '__main__':
    
    EventProcessorBase.setup_event_processors()
    
    SAEnginePlugin(cherrypy.engine, 'sqlite:///../datafiles/coredata.db').subscribe()
    cherrypy.tools.db = SATool()
    cherrypy.tree.mount(EventDataWebService(), '{0}/events'.format(MOUNT_LOCATION), EVENTDATASERVICE_CONF)
    cherrypy.tree.mount(PluginDataWebService(), '{0}/plugins'.format(MOUNT_LOCATION), PLUGINDATASERVICE_CONF)
    cherrypy.engine.start()
    cherrypy.engine.block()