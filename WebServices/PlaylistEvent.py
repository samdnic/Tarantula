# Some defined enums
from misc import enum

DeviceTypes = enum(CROSSPOINT="Crosspoint", VIDEODEVICE="Video", CGDEVICE="CG", PROCESSOR="Processor")


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