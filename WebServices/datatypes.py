import datetime

from sqlalchemy import Column, Integer, ForeignKey, BigInteger, Text
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base

# Note that these need to match the ordering in PlaylistDB.h
EVENTTYPES = [
              'fixed',
              'child',
              'manual'
              ]

EVENTSTATES = [
               'deleted',
               'ready',
               'done',
               'hold'
               ]

# Note that ordering needs to match that of playlist_device_type_t in PlaylistDB.h
DEVICEACTIONMAP = [
                        {
                         'name' : 'Crosspoint',
                         'items' : [
                                 {
                                  'id' : 0,
                                  'name' : 'Switch',
                                  'description' : 'Switch crosspoint output to connect to a different input',
                                  'parameters' : {
                                                  'output' : 'string',
                                                  'input' : 'string'
                                                  }
                                  }
                        ]},
                        {
                         'name' : 'Video',
                         'items' : [
                                 {
                                  'id' : 0,
                                  'name' : 'Play',
                                  'description' : 'Load and play a video file immediately',
                                  'parameters' : {
                                                  'filename' : 'string'
                                                  }
                                  },
                                 {
                                  'id' : 1,
                                  'name' : 'Load',
                                  'description' : 'Load a video file to be played',
                                  'parameters' : {
                                                  'filename' : 'string'
                                                  }
                                  },
                                 {
                                  'id' : 2,
                                  'name' : 'Play_Loaded',
                                  'description' : 'Play a video file previously loaded with Load',
                                  'parameters' : {}
                                  },
                                 {
                                  'id' : 3,
                                  'name' : 'Stop',
                                  'description' : 'Stop playing',
                                  'parameters' : {}
                                   }             
                        ]},
                        {
                         'name' : 'CG',
                         'items' : [
                                 {
                                  'id' : 0,
                                  'name' : 'Add',
                                  'description' : 'Adds a new CG event',
                                  'parameters' : {
                                                  'graphicname' : 'string',
                                                  'hostlayer' : 'int',
                                                  'templatedata' : 'map'
                                                  }
                                  },   
                                 {
                                  'id' : 1,
                                  'name' : 'Play',
                                  'description' : 'Plays template on by one step',
                                  'parameters' : {
                                                  'hostlayer' : 'int'
                                                  }                                          
                                  },          
                                 {
                                  'id' : 2,
                                  'name' : 'Update',
                                  'description' : 'Replace existing template data with new data',
                                  'parameters' : {
                                                  'hostlayer' : 'int',
                                                  'templatedata' : 'map'
                                                  }
                                  },
                                 {
                                  'id' : 3,
                                  'name' : 'Remove',
                                  'description' : 'Stop template and clear layer',
                                  'parameters' : {
                                                  'hostlayer' : 'int'
                                                  }
                                  },
                                 {
                                  'id' : 4,
                                  'name' : 'Parent',
                                  'description' : 'Does nothing - act as a placeholder for child event nesting',
                                  'parameters' : {}
                                  }
                        ]},
                        {
                         'name' : 'Processor',
                         'items' : [
                                 {
                                  'id' : 0,
                                  'name' : 'Process',
                                  'description' : 'Run the EventProcessor and replace it with the result',
                                  'parameters' : {}
                                  }
                        ]}
                     ]

# Helper functions for action map
def get_devicetype_fromname(name):
    """Find the index of a device type based on its name"""
    for i in range(0, len(DEVICEACTIONMAP)):
        if DEVICEACTIONMAP[i]['name'].lower() == name.lower():
            return i
    # If we didn't find it, throw
    raise KeyError

def get_action_fromname(name, devicetype):
    """Find the ID of an Action based on its name"""
    # If devicetype wasn't a number, look it up
    try:
        dt = int(devicetype)
    except ValueError:
        dt = get_devicetype_fromname(devicetype)
    
    for action in DEVICEACTIONMAP[dt]['items']:
        if action['name'].lower() == name.lower():
            return action['id']
    # If we didn't find it, throw
    raise KeyError   

def get_eventtype_fromname(name):
    """Find the index of an eventtype based on its name"""
    for i in range(0, len(EVENTTYPES)):
        if EVENTTYPES[i].lower() == name.lower():
            return i
    # If we didn't find it, throw
    raise KeyError     

def get_eventstate_fromname(name):
    """Find the index of an eventstatus based on its name"""
    for i in range(0, len(EVENTSTATES)):
        if EVENTSTATES[i].lower() == name.lower():
            return i
    # If we didn't find it, throw
    raise KeyError     

# Some SQLAlchemy ORM setup
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
            
    id = Column(Integer, primary_key = True, autoincrement = True)
    type = Column(Integer)
    trigger = Column(BigInteger, index = True)
    device = Column(Text)
    devicetype = Column(Integer)
    action = Column(Integer)
    duration = Column(Integer)
    parent = Column(Integer, ForeignKey(id), default=0)
    processed = Column(Integer, default=get_eventstate_fromname('ready'))
    lastupdate = Column(BigInteger)
    callback = Column(Text, default="")
    description = Column(Text)
    
    eventdata = relationship("PlaylistData")
    
    children = relationship("PlaylistEntry", backref=backref("parent_node", remote_side=id), cascade="save-update, merge, delete")
    
    def get_dict(self):
        """Return a dictionary version of the class for serialization"""
        
        try:
            dt = datetime.datetime.utcfromtimestamp(int(self.trigger))
            readable_time = datetime.datetime.isoformat(dt)
        except TypeError:
            readable_time = -1
            
        # Generate the data map
        extradata_map = {}
        for item in self.eventdata:
            extradata_map[item.key] = item.value
                
        data = {
                    'eventid'      : self.id,
                    'time'         : readable_time,
                    'description'  : self.description,
                    'duration'     : self.duration,
                    'parentid'     : self.parent,
                    'state'        : EVENTSTATES[self.processed],
                    'type'         : EVENTTYPES[self.type],
                    'preprocessor' : self.callback,
                    'extradata'    : extradata_map,
                    
                    'children'     : ([e.get_dict() for e in self.children]) if self.children != None else []
                }
        
        # Some things should only be included for normal events
        if (EVENTTYPES[self.type] == 'fixed'):
            data['devicename'] = self.device
            data['devicetype'] = DEVICEACTIONMAP[self.devicetype]['name']
            data['action'] = DEVICEACTIONMAP[self.devicetype]['items'][int(self.action)]['name']
            
        return data

    def get_copy(self):
        """Return an unlinked copy of this object"""
        newobj = PlaylistEntry(id=self.id, type=self.type, trigger=self.trigger, device=self.device,
                               devicetype=self.devicetype, action=self.action, processed=self.processed,
                               lastupdate=self.lastupdate, callback=self.callback, description=self.description)
        
        for item in self.eventdata:
            newobj.eventdata.append(PlaylistData(item.key, item.value))
            
        for child in self.children:
            newobj.children.append(child.get_copy())
            
        return newobj
    
    def get_data(self, key):
        """Find the value of a given key in the extradata list"""
        for datapoint in self.eventdata:
            if datapoint.key.lower() == key:
                return datapoint.value
        raise KeyError("Key {0} not found in data list".format(key))

class PlaylistData(Base):
    __tablename__ = "extradata"
    
    def __init__(self, key=None, value=None):
        self.key = key
        self.value = value
    
    id = Column(Integer, primary_key = True, autoincrement = True)
    eventid = Column(Integer, ForeignKey('events.id'))
    key = Column(Text)
    value = Column(Text)
    processed = Column(Integer)
    