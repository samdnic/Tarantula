# Some defined enums
from misc import enum

from sqlalchemy import Column, DateTime, String, Integer, ForeignKey, func, BigInteger, Text
from sqlalchemy.orm import *
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm.collections import *
DeviceTypes = enum(CROSSPOINT="Crosspoint", VIDEODEVICE="Video", CGDEVICE="CG", PROCESSOR="Processor")

Base = declarative_base()

"""(id INTEGER PRIMARY KEY AUTOINCREMENT, type INT, trigger INT64, "
            "device TEXT, devicetype INT, action, duration INT, parent INT, processed INT, lastupdate INT64, "
            "callback TEXT, description TEXT"""
            
"""(eventid INT, key TEXT, value TEXT, processed INT)"""

class PlaylistEntry_SQL(Base):
    __tablename__ = 'Default_events'
    
    id = Column(Integer, primary_key=True, autoincrement = True)
    type = Column(Integer)
    trigger = Column(BigInteger, index=True)
    device = Column(Text)
    devicetype = Column(Integer)
    action = Column(Integer)
    duration = Column(Integer)
    parent = Column(Integer, ForeignKey(id))
    processed = Column(Integer)
    lastupdate = Column(BigInteger)
    callback = Column(Text)
    description = Column(Text)
    
    children = relationship("PlaylistEntry_SQL", backref=backref("parent_id", remote_side=id), collection_class=attribute_mapped_collection('id'),)
    
    def get_dict(self):
        """Return a dictionary version of the class for serialization"""
        return {
                    'eventid' : self.id,
                    'time' : self.trigger,
                    'devicename' : self.device,
                    'devicetype' : self.devicetype,
                    'actionid' : self.action,
                    'description' : self.description,
                    'duration' : self.duration,
                    'parentid' : self.parent,
                    'preprocessor' : self.callback,
                    
                    'children' : ([self.children[e].get_dict() for e in self.children]) if self.children != None else []
                }

class PlaylistEntry(object):
    """Define a playlist entry roughly like it is stored in the database"""
    def __init__(self, time=None, device=None, devicetype=None, actionid=None,
                 description=None, duration=None, parentid=None, preprocessor=None,
                 extradata=None, childevents=None, eventid=None):
        self._eventid = eventid
        self._triggertime = time
        self._devicename = device
        self._devicetype = devicetype
        self._actionid = actionid
        
        self._description = description
        
        self._duration = duration
        self._parentid = parentid
        
        self._extradata = extradata
        
        self._preprocessor = preprocessor
        self._childevents = childevents
    
    def get_dict(self):
        """Return a dictionary version of the class for serialization"""
        return {
                    'eventid' : self._eventid,
                    'time' : self._triggertime,
                    'devicename' : self._devicename,
                    'devicetype' : self._devicetype,
                    'actionid' : self._actionid,
                    'description' : self._description,
                    'duration' : self._duration,
                    'parentid' : self._parentid,
                    'preprocessor' : self._preprocessor,
                    
                    'children' : ([e.get_dict() for e in self._childevents]) if self._childevents != None else []
                }