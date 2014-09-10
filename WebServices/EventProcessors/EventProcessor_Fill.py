import xml.etree.ElementTree as XMLTree

from sqlalchemy import Column, Integer, ForeignKey, Text, DateTime, desc, select, func, join, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.expression import case
import sqlalchemy.orm

import cherrypy
from cherrypy.process.plugins import Monitor

import datetime

import misc
from EventProcessorBase import EventProcessorBase
from datatypes import PlaylistEntry, PlaylistData
import datatypes

class EventProcessor_Fill(EventProcessorBase):
    
    _weightpoints = []
    _conditionlist = []
    
    _gentoplevel = False
    _fileweightscaling = 1
    
    _continuityevent = None
    
    _continuitymin = datetime.timedelta(seconds=0)
    _structureitems = []
    _durationoffset = datetime.timedelta(seconds=0)
    _repeattofill = False
    
    _tabletag = None
    
    Base = declarative_base()    
    
    class VideoEntry(Base):
        __tablename__ = 'videos'
        
        id = Column(Integer, primary_key = True, autoincrement = True)
        duration = Column(Integer)
        filename = Column(Text)
        description = Column(Text)    
        typename = Column(Text)
        devicename = Column(Text)
        weight = Column(Integer)
    
    class VideoBucket(Base):
        __tablename__ = 'buckets'
        
        id = Column(Integer, primary_key=True, autoincrement=True)
        
        bucketcount = Column(Integer)
        
        bucketstart = Column(DateTime)
        
        buckettag = Column(Integer)
        
        video_id = Column(Integer, ForeignKey('videos.id'))
    
    """Generates events for idents, trailers and continuity graphics to fill schedules"""
    def __init__(self, xmltree):
        """Parse the complex configuration defining the fill algorithm, and confirm access to the DB"""
        # Parse the weight points data
        for point in xmltree.find('WeightPoints').findall('WeightPoint'):
            timedata = point.find('Time').text
            timeunit = point.find('Time').get('units', 'seconds')
            timepoint = misc.parse_duration(int(timedata), timeunit.lower())
            weight = point.find('Weight').text
            
            self._conditionlist.append((self.VideoBucket.buckettag == len(self._weightpoints), 
                                        self.VideoBucket.bucketcount * weight))
            
            self._weightpoints.append({
                                 'time' :   timepoint,
                                 'weight' : weight
                                 })
            
        self._weightpoints[0]['time'] = None
            
        # Parse some misc config data
        self._gentoplevel = (xmltree.find('GenerateTopLevel').text.lower() == 'true')
        self._fileweightscaling = int(xmltree.find('FileWeight').text)
        self._dbfile = xmltree.find('DBFile').text.lower()
        self._repeattofill = (xmltree.find('EnableFill').text.lower() == 'true')
        
        try:
            offsetdata = xmltree.find('ItemOffset').text
            offsetunits = xmltree.find('ItemOffset').get('units', 'seconds')
            self._offsetfactor = misc.parse_duration(offsetdata, offsetunits)
        except AttributeError:
            #This parameter is optional, set to zero
            self._offsetfactor = datetime.timedelta(seconds=0)
        
        # Parse the continuity fill section, if active
        element = xmltree.find('ContinuityFill')
        if element != None:
            lengthdata = element.find('MinimumTime').text
            lengthunits = element.find('MinimumTime').get('units', 'seconds')
            self._continuitymin = misc.parse_duration(int(lengthdata), lengthunits)
            
            # Generate add and remove CG events and a parent
            self._continuityevent = PlaylistEntry()
            self._continuityevent.device = element.find('Device').text
            self._continuityevent.type = datatypes.get_eventtype_fromname('fixed')
            self._continuityevent.devicetype = datatypes.get_devicetype_fromname('CG')
            self._continuityevent.action = datatypes.get_action_fromname('Parent', 'CG')
            self._continuityevent.eventdata.append(PlaylistData('hostlayer', 
                                                                element.find('HostLayer').text))
            
            
            addevent = PlaylistEntry(parent_node = self._continuityevent)
            addevent.eventdata.append(PlaylistData('graphicname', 
                                                    element.find('GraphicName').text))
            addevent.callback = element.find('PreProcessor').text
            addevent.eventdata.append(PlaylistData('hostlayer', 
                                                    element.find('HostLayer').text))
            addevent.device = element.find('Device').text
            addevent.type = datatypes.get_eventtype_fromname('fixed')
            addevent.devicetype = datatypes.get_devicetype_fromname('CG')
            addevent.action = datatypes.get_action_fromname('Add', 'CG')
            addevent.duration = 1
            addevent.eventdata.append(PlaylistData('nexttext', 'ppfill'))
            addevent.eventdata.append(PlaylistData('thentext', 'ppfill'))
            
            removeevent = PlaylistEntry(parent_node = self._continuityevent)
            removeevent.eventdata.append(PlaylistData('hostlayer', 
                                                      element.find('HostLayer').text))
            removeevent.device = element.find('Device').text
            removeevent.devicetype = datatypes.get_devicetype_fromname('CG')
            removeevent.type = datatypes.get_eventtype_fromname('fixed')
            removeevent.action = datatypes.get_action_fromname('Remove', 'CG')
            removeevent.duration = 1
            
        # Parse the fill structure data
        for item in xmltree.find('StructureData').findall('StructureItem'):
            typename = item.find('Type').text
            device = item.find('Device').text
            devicetype = item.find('DeviceType').text
            action = item.find('Action').text
            
            self._structureitems.append({
                                         'Type'       : typename,
                                         'Device'     : device,
                                         'DeviceType' : datatypes.get_devicetype_fromname(devicetype),
                                         'Action'     : datatypes.get_action_fromname(action, devicetype)
                                         })   
            
        # Open DB connection            
        self.engine = create_engine('sqlite:///{0}'.format(self._dbfile))
        self.DBSession = sqlalchemy.orm.sessionmaker(bind=self.engine)
            
        # Create the DB tables if they don't exist   
        self.Base.metadata.create_all(self.engine)     
        
        # Run a first bucket aging
        self.age_buckets()
        
        # Activate scheduled ageing
        Monitor(cherrypy.engine, self.age_buckets, 
                frequency=self._weightpoints[1]['time'].total_seconds()).subscribe()
        
    def handleevent(self, event):
        """Actually generate a filled event set"""
        parent = event
        import time
        start = time.time()
        # Get singlemode flag, used to only generate one set of events
        singlemode = False
        for datapoint in event.eventdata:
            if (datapoint.key.lower() == 'singleshotmode' 
                and datapoint.value.lower() == 'true'):
                singlemode = True
                break
        
        duration = (misc.parse_duration(event.duration, 'seconds') - 
                    self._continuitymin - self._durationoffset)
        
        # Check that event is long enough for continuity time
        if (duration < datetime.timedelta(seconds=0)):
            duration = datetime.timedelta(seconds=0)
            
        runningtrigger = datetime.datetime.utcfromtimestamp(event.trigger)
        itemkey = 0 
        
        # Create a database session
        dbsession = self.DBSession()
            
        # Generate events until we run out of time or ideas
        while duration > datetime.timedelta(seconds=0):
            # Get the corresponding structure data entry
            item = self._structureitems[itemkey]
            
            video = self.get_file(duration, item['Type'], dbsession)
            
            if video != None:
                newevent = PlaylistEntry(parent_node=parent)
                newevent.duration = video.duration
                newevent.trigger = misc.get_timestamp(runningtrigger)
                newevent.description = video.description
                newevent.type = 0 # 0 should be "fixed" 
                newevent.device = item['Device']
                newevent.devicetype = item['DeviceType']
                newevent.action = item['Action']
                newevent.eventdata.append(PlaylistData('filename', video.filename))
                
                durationdelta = misc.parse_duration(video.duration, 'seconds')
                
                runningtrigger += durationdelta + self._durationoffset 
                duration -= durationdelta
                
                if itemkey < (len(self._structureitems) - 1):
                    itemkey += 1
                elif not self._repeattofill or singlemode:
                    break
            else:
                break
                                      
        # Finally generate continuity if needed (singlemode off or nothing created)
        if parent.children == None or not singlemode:
            continuity = self._continuityevent.get_copy()
            
            continuity.trigger = misc.get_timestamp(runningtrigger)
            continuity.duration = (duration + self._continuitymin).total_seconds()
            continuity.children[0].trigger = misc.get_timestamp(runningtrigger)
            continuity.children[1].trigger = misc.get_timestamp(runningtrigger + duration)
            
            parent.children.append(continuity)
            
        dbsession.commit()
        print "Run in {0}".format(time.time() - start)
        return parent
                
        
    def get_file(self, duration=None, typename=None, dbsession=None):  
        """Find the current best file and mark a play for it"""
        # Assemble a query to get the details
        query = select([
                        self.VideoEntry.id, 
                        (func.sum(case(self._conditionlist)) * self.VideoEntry.weight).label('weights')
                        ],  
                    group_by = self.VideoBucket.video_id, 
                    order_by = ('weights', func.random()),
                    limit = 1).select_from(join(self.VideoEntry, self.VideoBucket, isouter=True))
        
        # Add some additional criteria
        if duration != None:
            query = query.where(self.VideoEntry.duration <= duration.total_seconds())
            
        if typename != None:
            query = query.where(self.VideoEntry.typename == typename)
        
        # Get the best file back
        result = self.engine.execute(query).fetchone()
        
        if result == None:
            return None
            
        # Get the actual video entry based on its ID
        if dbsession == None:
            commitnow = True
            dbsession = self.DBSession()
        else:
            commitnow = False
            
        detail = dbsession.query(self.VideoEntry).filter(self.VideoEntry.id == result['id']).one()
        
        # Mark this file as played now
        self.append_or_create(0, 1, detail.id, self._weightpoints[1]['time'], dbsession=dbsession)
        
        if commitnow:
            dbsession.commit()
        
        return detail
    
    def append_or_create(self, newtag, incrementvalue, video_id, threshold, timenow = None, dbsession = None):
        """Either add incrementvalue to the bucket matching newtag and video_id, 
        or if the start is > threshold, start a new one"""
        
        if timenow == None:
            timenow = datetime.datetime.utcnow()
            
        if dbsession == None:
            dbsession = self.session
            
        try:
            nextupbucket = (dbsession.query(self.VideoBucket).filter(self.VideoBucket.buckettag == newtag).
                            filter(self.VideoBucket.video_id == video_id).order_by(desc(self.VideoBucket.bucketstart)).first())
        except sqlalchemy.orm.exc.NoResultFound:
            nextupbucket = None
                    
        # Test if this bucket is old enough to create a fresh one
        if ((nextupbucket == None) or 
            (timenow - nextupbucket.bucketstart > threshold)):
            # OK, create a fresh bucket from now
            newbucket = self.VideoBucket()
            newbucket.buckettag = newtag
            newbucket.bucketcount = incrementvalue
            newbucket.video_id = video_id            
            newbucket.bucketstart = timenow
            
            dbsession.add(newbucket)
        else:
            nextupbucket.bucketcount += incrementvalue
    
    def age_buckets(self, dbsession = None, timenow = None):
        """Move data into older buckets as it ages"""
        if timenow == None:
            timenow = datetime.datetime.utcnow()
            
        if dbsession == None:
            dbsession = self.DBSession()
            commitnow = True
        else:
            commitnow = False
        
        # Loop over each tag to age out older buckets
        for i in range (0, len(self._weightpoints)-1):
            # Find where bucketstart < now - length and add to next tag up
            res = (dbsession.query(self.VideoBucket).filter(self.VideoBucket.buckettag == i).
                    filter(self.VideoBucket.bucketstart < (timenow - self._weightpoints[i+1]['time'])).all())
            for result in res:           
                # Deal with the special case of last bucket
                if (i+1) == (len(self._weightpoints)-1):
                    threshold = datetime.timedelta.max
                else:
                    threshold = self._weightpoints[i+1]['time']
                    
                self.append_or_create(i+1, result.bucketcount, result.video_id, threshold, timenow, dbsession)
                    
                # Delete current result
                dbsession.delete(result)
                
        if commitnow:
            dbsession.commit()