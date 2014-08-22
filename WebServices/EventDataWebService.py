import cherrypy
import datetime
import sqlalchemy

from PlaylistEntry import PlaylistEntry
import misc

EVENTDATASERVICE_CONF = {
        '/': {
            'request.dispatch': cherrypy.dispatch.MethodDispatcher(),
            'tools.db.on'     : True,
        }
    }

class EventDataWebService(object):
    _DEFAULT_TIME_RANGE = datetime.timedelta(hours=2)
    
    exposed = True

    @cherrypy.tools.accept(media='text/plain')
    @cherrypy.tools.json_out()
    def GET(self, eventid=None, start=None, end=None):
        """Return either a queried list of events, or a specific event"""
        if eventid != None:
            database = cherrypy.request.db
            
            dataarray = database.query(PlaylistEntry).filter(PlaylistEntry.id == eventid).all()
            
            if len(dataarray) == 0:
                raise cherrypy.HTTPError(404, "Event with id {0} not found".format(eventid))
            else:
                return [e.get_dict() for e in dataarray]
            
        else:
            if start != None:
                try:
                    start_parse = misc.parse_time(start)
                except TypeError:
                    raise cherrypy.HTTPError(500, "Unable to process timestamp {0}".format(start))    
            else:
                start_parse = datetime.datetime.now()
                
            if end != None:
                try:
                    end_parse = misc.parse_time(end)
                except TypeError:
                    raise cherrypy.HTTPError(500, "Unable to process timestamp {0}".format(end)) 
            else:
                end_parse = start_parse + self._DEFAULT_TIME_RANGE
                
            if end_parse < start_parse:
                raise cherrypy.HTTPError(400, "End time must be after start time!")
                
            database = cherrypy.request.db
            
            start_ts = misc.get_timestamp(start_parse)
            end_ts = misc.get_timestamp(end_parse)
            dataarray = database.query(PlaylistEntry).filter(sqlalchemy.and_(PlaylistEntry.trigger > start_ts,
                                                                             PlaylistEntry.trigger < end_ts)).all()
                                                                             
            return [e.get_dict() for e in dataarray]

if __name__ == '__main__':
    
    from SQLEngine import SAEnginePlugin, SATool
    SAEnginePlugin(cherrypy.engine, 'sqlite:///test3.db').subscribe()
    cherrypy.tools.db = SATool()
    #cherrypy.tree.mount(EventDataWebService(), '/api/v1.0/events', EVENTDATASERVICE_CONF)
    #cherrypy.engine.start()
    #cherrypy.engine.block()
    
    cherrypy.quickstart(EventDataWebService(), '/', EVENTDATASERVICE_CONF)