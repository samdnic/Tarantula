import cherrypy
import datetime
import sqlalchemy.orm

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
            
            try:
                dataarray = database.query(PlaylistEntry).filter(PlaylistEntry.id == eventid).one()
            except sqlalchemy.orm.exc.NoResultFound:
                raise cherrypy.HTTPError(404, "Event with id {0} not found".format(eventid))

            return dataarray.get_dict()
            
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
                                                                             PlaylistEntry.trigger < end_ts,
                                                                             PlaylistEntry.parent == 0)).all()
                                                                             
            return [e.get_dict() for e in dataarray]
        
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def POST(self):
        """Insert a new event, and return it with ID"""
        input_data = cherrypy.request.json
        
        newentry = self._new_recurse(input_data, None)
        
        # Persist the new entry
        database = cherrypy.request.db
        database.add(newentry)
        database.commit()
        
        cherrypy.response.status = 201
        return newentry.get_dict()
    
    @cherrypy.tools.json_in()
    def PUT(self, eventid):
        """Update a single event. Doesn't do children"""
        #Some input validation
        if eventid == None:
            raise cherrypy.HTTPError(400, "No event ID specified")
        
        input_data = cherrypy.request.json
        
        updateentry = self._new_recurse(input_data, None, True)
        
        database = cherrypy.request.db
        
        database.merge(updateentry)

        # Commit the result
        database.commit()
        
        cherrypy.response.status = 204
        
    def DELETE(self, eventid):
        """Delete event. Will recurse"""
        if eventid == None:
            raise cherrypy.HTTPError(400, "No event ID specified")
        
        database = cherrypy.request.db
        
        try:
            item = database.query(PlaylistEntry).filter(PlaylistEntry.id == eventid).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise cherrypy.HTTPError(404, "No event found for ID {0}. Maybe you already deleted it?".format(eventid))
        
        database.delete(item)
        database.commit()
        
        cherrypy.response.status = 204
        
    def _new_recurse(self, input_data, target_entry, set_id = False):
        """Fill a new PlaylistEntry and return it or add it as a child, then recurse"""
        # Create a new entry (with parent set if child)
        if target_entry != None:
            newentry = PlaylistEntry(parent_node = target_entry)
        else:
            newentry = PlaylistEntry()
        
        # Populate fields
        newentry.trigger = misc.get_timestamp(misc.parse_time(input_data['time']))
        newentry.device = input_data['devicename']
        newentry.devicetype = input_data['devicetype']
        newentry.action = input_data['actionid']
        newentry.duration = input_data['duration']
        newentry.type = input_data['type']
        newentry.callback = input_data['preprocessor']
        newentry.description = input_data['description']
        
        if set_id == True:
            newentry.id = input_data['eventid']
    
        try:
            newentry.parent = input_data['parentid']
        except KeyError:
            # If top level, set parent = 0
            if target_entry == None:
                newentry.parent = 0
            
        newentry.processed = 0
        newentry.lastupdate = misc.get_timestamp(datetime.datetime.now())
        
        # Recurse into children
        for item in input_data['children']:
            self._new_recurse(item, newentry, set_id)
        
        # Append to parent if needed
        if target_entry == None:
            return newentry
    
if __name__ == '__main__':
    
    from SQLEngine import SAEnginePlugin, SATool
    SAEnginePlugin(cherrypy.engine, 'sqlite:///../datafiles/coredata.db').subscribe()
    cherrypy.tools.db = SATool()
    
    cherrypy.quickstart(EventDataWebService(), '/', EVENTDATASERVICE_CONF)