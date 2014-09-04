import xml.etree.ElementTree as XMLTree

from sqlalchemy import Column, Integer, ForeignKey, Text, DateTime, desc, select, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql.expression import case
from sqlalchemy import create_engine
import sqlalchemy.orm

import datetime

import misc
from EventProcessorBase import EventProcessorBase
from datatypes import PlaylistEntry, PlaylistData


class EventProcessor_Fill(EventProcessorBase):
    
    _weightpoints = []
    _conditionlist = []
    
    _gentoplevel = False
    _fileweightscaling = 1
    
    _continuitydata = None
    _structureitems = []
    
    _tabletag = None
    
    Base = declarative_base()    
    
    class VideoEntry(Base):
        __tablename__ = 'videos'
        
        id = Column(Integer, primary_key = True, autoincrement = True)
        duration = Column(Integer)
        filename = Column(Text)
        description = Column(Text)    
    
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

        # Parse the continuity fill section, if active
        if (xmltree.find('EnableFill').text.lower() == 'true'):
            self._continuitydata = {}
            element = xmltree.find('ContinuityFill')
            self._continuitydata['Device'] = element.find('Device').text
            self._continuitydata['GraphicName'] = element.find('GraphicName').text
            self._continuitydata['PreProcessor'] = element.find('PreProcessor').text
            self._continuitydata['HostLayer'] = int(element.find('HostLayer').text)
            
            lengthdata = element.find('MinimumTime').text
            lengthunits = element.find('MinimumTime').get('units', 'seconds')
            self._continuitydata['MinimumTime'] = misc.parse_duration(int(lengthdata), lengthunits)
            
        # Parse the fill structure data
        for item in xmltree.find('StructureData').findall('StructureItem'):
            typename = item.find('Type').text
            device = item.find('Device').text
            
            self._structureitems.append({
                                         'Type'   : typename,
                                         'Device' : device
                                         })   
            
        # Open DB connection            
        engine = create_engine('sqlite:///{0}'.format(self._dbfile))
        DBSession = sessionmaker(bind=engine)
        self.session = DBSession()
            
        # Create the DB tables if they don't exist   
        self.Base.metadata.create_all(engine)     
        
        # Run a first bucket aging
        self.age_buckets()
        
    def handleevent(self, event):
        """Actually generate a filled event set"""
        
        
    def get_file(self, duration=None, typename=None):  
        """Find the current best file and mark a play for it"""
        # Assemble a query to get the details
        query = select([
                        self.VideoBucket.video_id, 
                        func.sum(case(self._conditionlist)).label('weights')
                        ], 
                    self.VideoEntry.id == self.VideoBucket.video_id, 
                    group_by = self.VideoBucket.video_id, 
                    order_by = ('weights', func.random()),
                    limit = 1)
        
        # Add some additional criteria
        if duration != None:
            query = query.where(self.VideoEntry.duration <= duration)
            
        if typename != None:
            query = query.where(self.VideoEntry.typename == typename)
        
        # Get the best file back
        result = self.engine.execute(query).fetchone()
        
        #TODO What happens if we get nothing?
            
        # Get the actual video entry based on its ID
        detail =self. session.query(self.VideoEntry).filter(self.VideoEntry.id == result['video_id']).one()
        
        # Mark this file as played now
        self.add_play(detail.id)
        
        # Must commit immediately so next file isn't the same
        self.session.commit()
        
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
            dbsession = self.session
        
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