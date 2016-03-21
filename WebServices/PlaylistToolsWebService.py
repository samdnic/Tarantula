import cherrypy
import datetime
import sqlalchemy
import sqlalchemy.orm
import sqlalchemy.sql.expression

import EventProcessorBase
from datatypes import PlaylistEntry
import datatypes
import misc


PLAYLISTTOOLSSERVICE_CONF = {
        '/': {
            'request.dispatch': cherrypy.dispatch.Dispatcher(),
            'tools.db.on'     : True,
        }
    }

class PlaylistToolsWebService(object):
    _DEFAULT_TIME_RANGE = datetime.timedelta(days=1)
    _SHUNT_FUDGE_FACTOR = 5

    @cherrypy.tools.accept(media='text/plain')
    @cherrypy.expose
    def release(self, eventid, eventend=None):
        """Mark the end of a manual hold, and perform a shunt"""
        database = cherrypy.request.db
        
        # Go find the event
        try:
            eventdata = database.query(PlaylistEntry).filter(PlaylistEntry.id == eventid).one()
        except sqlalchemy.orm.exc.NoResultFound:
            raise cherrypy.HTTPError(404, "Event with id {0} not found".format(eventid))
        
        # State update
        eventdata.processed = datatypes.get_eventstate_fromname('done')
        
        # Parse the time it supposedly ended (if given)
        if eventend != None:
            timepoint = misc.parse_time(eventend)
        else:
            timepoint = datetime.datetime.utcnow()
            
        # How far off targeted end time were we?
        plannedend = misc.parse_time(eventdata.trigger) + misc.parse_duration(eventdata.duration, 'seconds')
        
        # The difference may be positive (we ended late) or negative (early), but either way we can shunt
        difference = timepoint - plannedend
        
        
        shunttime = datetime.datetime.isoformat(plannedend)
        self.shunt(shunttime, plannedend)

        database.commit()
        
        cherrypy.response.status = 200
        return "Success!"
        
    @cherrypy.tools.accept(media='text/plain')    
    @cherrypy.expose
    def shunt(self, timepoint, originalend):
        """Push/pull the playlist by a specified offset"""
        
        timepoint = misc.get_timestamp(misc.parse_time(timepoint))

        if not isinstance(originalend, datetime.datetime):
            originalend = misc.parse_time(originalend)

        originalend = misc.get_timestamp(originalend)
        duration = timepoint - originalend
        
        # Alex Williams devised this clever little jewel
        database = cherrypy.request.db
        
        while abs(duration) > 0:
            # Find the next empty space                        
            space_start = database.scalar(sqlalchemy.sql.expression.text(
                    'SELECT trigger + duration ' +
                       'FROM events AS a ' + 
                       'WHERE trigger > :trigtime AND parent IS NULL AND NOT EXISTS ' +
                            '(SELECT NULL ' +
                            'FROM events AS b ' +
                            'WHERE b.trigger - (a.trigger + a.duration) < ' + str(self._SHUNT_FUDGE_FACTOR) + ' ' +
                            'AND (a.trigger + a.duration) < (b.trigger + b.duration) ' +
                            'AND parent IS NULL ) '
                        'ORDER BY a.trigger ASC ' +
                        'LIMIT 1').bindparams(trigtime = originalend))
            
            # Check how long the space is
            space_size = database.scalar(sqlalchemy.sql.expression.text(
                    'SELECT trigger - :space ' +
                        'FROM events ' +
                        'WHERE trigger IS NOT NULL ' +
                        'AND trigger > :space ' +
                        'ORDER BY trigger ASC ' +
                        'LIMIT 1').bindparams(space = space_start))
            
            if space_size != None and space_size < duration:
                updatesize = space_size
                duration = duration - space_size
            else:
                # In the negative duration case this will immediately break the loop
                updatesize = duration
                duration = 0
            
            # If duration was negative, we only shunt back to first gap    
            database.execute(sqlalchemy.sql.expression.text(
                    'UPDATE events ' +
                     'SET trigger = trigger + :update ' +
                     'WHERE trigger >= :original AND trigger < :end').bindparams(update = updatesize,
                                                                                  original = originalend,
                                                                                  end = space_start))                                              
                
        cherrypy.response.status = 200
        return "Success!"                                                         
    
if __name__ == '__main__':
    
    from SQLEngine import SAEnginePlugin, SATool
    SAEnginePlugin(cherrypy.engine, 'sqlite:///../datafiles/coredata.db').subscribe()
    cherrypy.tools.db = SATool()
    
    EventProcessorBase.setup_event_processors()
    
    cherrypy.quickstart(PlaylistToolsWebService(), '/', PLAYLISTTOOLSSERVICE_CONF)