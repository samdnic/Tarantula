import cherrypy

from SQLEngine import SAEnginePlugin, SATool

from EventDataWebService import EventDataWebService, EVENTDATASERVICE_CONF

MOUNT_LOCATION = '/api/v1.0'


if __name__ == '__main__':
    SAEnginePlugin(cherrypy.engine, 'sqlite:///test3.db').subscribe()
    cherrypy.tools.db = SATool()
    cherrypy.tree.mount(EventDataWebService(), '{0}/events'.format(MOUNT_LOCATION), EVENTDATASERVICE_CONF)
    cherrypy.engine.start()
    cherrypy.engine.block()