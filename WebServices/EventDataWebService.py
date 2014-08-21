import random
import string

import cherrypy

from PlaylistEvent import *

events = [
    PlaylistEntry(10, "test", DeviceTypes.VIDEODEVICE, 1, "Test123", 4, 1, "", None, None, eventid=2),
    PlaylistEntry(10, "test", DeviceTypes.VIDEODEVICE, 1, "Test123", 4, 1, "", None, [PlaylistEntry(10, "test3"),], eventid=3)
]

EVENTDATASERVICE_CONF = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.db.on'     : True,
        }
    }

class EventDataWebService(object):
    exposed = True

    @cherrypy.tools.accept(media='text/plain')
    @cherrypy.tools.json_out()
    def GET(self, eventid):
        #return [e.get_dict() for e in events]
        database = cherrypy.request.db
        
        dataarray = database.query(PlaylistEntry_SQL).filter(PlaylistEntry_SQL.id == eventid).all()
        return [e.get_dict() for e in dataarray]


if __name__ == '__main__':
    
    from SQLEngine import *
    SAEnginePlugin(cherrypy.engine, 'sqlite:///test3.db').subscribe()
    cherrypy.tools.db = SATool()
    #cherrypy.tree.mount(EventDataWebService(), '/api/v1.0/events', EVENTDATASERVICE_CONF)
    #cherrypy.engine.start()
    #cherrypy.engine.block()
    
    cherrypy.quickstart(EventDataWebService(), '/', EVENTDATASERVICE_CONF)