import cherrypy
import datetime
import sqlalchemy
import sqlalchemy.orm

import EventProcessorBase
from datatypes import PlaylistEntry
import datatypes
import misc


SCHEDULEDATASERVICE_CONF = {
        '/': {
            'request.dispatch': cherrypy.dispatch.Dispatcher(),
            'tools.db.on'     : True,
        }
    }

class ScheduleDataWebService(object):
    _DEFAULT_TIME_RANGE = datetime.timedelta(days=1)

    @cherrypy.tools.accept(media='text/plain')
    @cherrypy.tools.json_out()
    @cherrypy.expose
    def index(self, start=None, end=None):
        """Return today's events"""       
        if start != None:
            try:
                start_parse = misc.parse_time(start)
            except TypeError:
                raise cherrypy.HTTPError(500, "Unable to process timestamp {0}".format(start))    
        else:
            today = datetime.datetime.now().date()
            start_parse = datetime.datetime(today.year, today.month, today.day)
            
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
                                                                         PlaylistEntry.parent == None)).all()
                                                                         
        return [self._get_public_dict(e) for e in dataarray]
    
    @cherrypy.tools.accept(media='text/plain')
    @cherrypy.tools.json_out()
    @cherrypy.expose
    def nowplaying(self):
        """Return whatever event should currently be running (unless we've had a sched crash)"""
        database = cherrypy.request.db
        timepoint = misc.get_timestamp(datetime.datetime.now())
        
        # First, do we have a manual hold currently active?
        try:
            manualevent = database.query(PlaylistEntry).filter(
                        PlaylistEntry.processed == datatypes.get_eventstate_fromname('hold')).one()
                        
            # OK, let's walk the tree to grab the top level
            while manualevent.parent != None:
                manualevent = manualevent.parent
                
            return self._get_public_dict(manualevent)
        
        except sqlalchemy.orm.exc.NoResultFound:
            pass

        # Normal events then.
        try:
            currentevent = database.query(PlaylistEntry).filter(sqlalchemy.and_(PlaylistEntry.trigger < timepoint,
                                                                         PlaylistEntry.trigger + PlaylistEntry.duration > timepoint,
                                                                         PlaylistEntry.parent == None)).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return []
        
        return self._get_public_dict(currentevent)
    
    @cherrypy.tools.accept(media='text/plain')
    @cherrypy.tools.json_out()
    @cherrypy.expose
    def nextplaying(self, count=1): 
        """Return the specified number of upcoming events, or the first"""
        database = cherrypy.request.db
        timepoint = misc.get_timestamp(datetime.datetime.now())
        
        dataarray = database.query(PlaylistEntry).filter(sqlalchemy.and_(PlaylistEntry.trigger > timepoint,
                                                                         PlaylistEntry.parent == None)).order_by(PlaylistEntry.trigger).all()
                                                                         
        return [self._get_public_dict(e) for e in dataarray]
        
    def _get_public_dict(self, playlist_entry):
        """Strip out all the internal data from a playlist entry for a "public" API"""
        try:
            dt = datetime.datetime.utcfromtimestamp(int(playlist_entry.trigger))
            readable_time = datetime.datetime.isoformat(dt)
        except TypeError:
            readable_time = -1
            
        data = {
                    'eventid'      : playlist_entry.id,
                    'time'         : readable_time,
                    'description'  : playlist_entry.description,
                    'duration'     : playlist_entry.duration,
                } 
        
        return data                                                             
                                                                         
    
if __name__ == '__main__':
    
    from SQLEngine import SAEnginePlugin, SATool
    SAEnginePlugin(cherrypy.engine, 'sqlite:///../datafiles/coredata.db').subscribe()
    cherrypy.tools.db = SATool()
    
    EventProcessorBase.setup_event_processors()
    
    cherrypy.quickstart(ScheduleDataWebService(), '/', SCHEDULEDATASERVICE_CONF)