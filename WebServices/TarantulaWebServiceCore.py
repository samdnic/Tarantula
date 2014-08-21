import cherrypy

from cherrypy.process import wspbus

from SQLEngine import * 

from EventDataWebService import EventDataWebService, EVENTDATASERVICE_CONF


if __name__ == '__main__':
    SAEnginePlugin(cherrypy.engine, 'sqlite:///test3.db').subscribe()
    cherrypy.tools.db = SATool()
    cherrypy.tree.mount(EventDataWebService(), '/api/v1.0/events', EVENTDATASERVICE_CONF)
    cherrypy.engine.start()
    cherrypy.engine.block()