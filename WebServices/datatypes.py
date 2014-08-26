import misc
import datetime

from sqlalchemy import Column, Integer, ForeignKey, BigInteger, Text
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base
DeviceTypes = misc.enum(CROSSPOINT="Crosspoint", VIDEODEVICE="Video", CGDEVICE="CG", PROCESSOR="Processor")

Base = declarative_base()

class PluginData(Base):
    __tablename__ = 'plugins'
    
    instancename = Column(Text, primary_key=True)
    pluginname = Column(Text)
    type = Column(Text)
    status = Column(Text)
    
    def get_dict(self):
        """Return a dictionary version for serialisation"""
        return {
                    'instancename' : self.instancename,
                    'pluginname'   : self.pluginname,
                    'type'         : self.type,
                    'status'       : self.status
                }
        

class PlaylistEntry(Base):
    __tablename__ = 'events'
    
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
    
    children = relationship("PlaylistEntry", backref=backref("parent_node", remote_side=id), cascade="save-update, merge, delete")
    
    def get_dict(self):
        """Return a dictionary version of the class for serialization"""
        
        try:
            readable_time = datetime.datetime.isoformat(datetime.datetime.fromtimestamp(self.trigger))
        except TypeError:
            readable_time = -1
        
        return {
                    'eventid'      : self.id,
                    'time'         : readable_time,
                    'devicename'   : self.device,
                    'devicetype'   : self.devicetype,
                    'actionid'     : self.action,
                    'description'  : self.description,
                    'duration'     : self.duration,
                    'parentid'     : self.parent,
                    'type'         : self.type,
                    'preprocessor' : self.callback,
                    
                    'children'     : ([e.get_dict() for e in self.children]) if self.children != None else []
                }
