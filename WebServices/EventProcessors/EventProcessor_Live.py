from EventProcessorBase import EventProcessorBase
from datatypes import PlaylistEntry, PlaylistData
import datatypes

import misc


class EventProcessor_Live(EventProcessorBase):
    def __init__(self, xmltree=None):
        """Read some configuration data"""
        
        # CG Overlay fill stuff
        self._cgdevice = xmltree.find('CGDevice').text
        self._nownextname = xmltree.find('NowNextName').text
        self._nownextlayer = int(xmltree.find('NowNextHostLayer').text)
        
        self._nownextmin = misc.parse_duration(float(xmltree.find('NowNextMin').text), 
                                               xmltree.find('NowNextMin').get('units', 'seconds'))
        self._nownextperiod = misc.parse_duration(float(xmltree.find('NowNextPeriod').text), 
                                               xmltree.find('NowNextPeriod').get('units', 'seconds'))
        self._nownextduration = misc.parse_duration(float(xmltree.find('NowNextDuration').text), 
                                               xmltree.find('NowNextDuration').get('units', 'seconds'))
        
        # Trailer fill stuff
        self._continuitygenerator = xmltree.find('FillProcessorName').text
        continuitylength = xmltree.find('FillLength').text
        continuityunits = xmltree.find('FillLength').get('units', 'seconds')
        self._continuitylength = misc.parse_duration(int(continuitylength), continuityunits)
        
        # VT Clock stuff
        self._clockdevice = xmltree.find('VTDevice').text
        self._clockname = xmltree.find('VTClockFilename').text
        self._clocklength = misc.parse_duration(float(xmltree.find('VTClockDuration').text),
                                                xmltree.find('VTClockDuration').get('units', 'seconds'))
        
        self._livefilename = xmltree.find('LiveFilename').text
        self._videodevice = xmltree.find('VideoDevice').text
        
        # Nulls checking
        if (self._cgdevice == None or self._nownextname == None or self._continuitygenerator == None or
            self._clockdevice == None or self._clockname == None or self._livefilename == None or
            self._videodevice == None):
            raise KeyError("A key piece of config data was not found! Failing!")
        
    def handleevent(self, event):
        """Generate the string of fill, video, VT and CG events for a live show"""
        
        # Create the container event
        newevent = PlaylistEntry()
        
        newevent.description = event.description
        newevent.type = datatypes.get_eventtype_fromname('fixed')
        newevent.trigger = event.trigger
        newevent.device = event.device
        newevent.duration = (misc.parse_duration(event.duration, 'seconds') 
                             + self._continuitylength).total_seconds()
        newevent.devicetype = datatypes.get_devicetype_fromname('Processor')
        newevent.action = datatypes.get_action_fromname('Process', newevent.devicetype)
        
        # Construct a trailer fill event
        fillevent = PlaylistEntry(parent_node = newevent)
        fillevent.trigger = event.trigger
        fillevent.device = self._continuitygenerator
        fillevent.devicetype = datatypes.get_devicetype_fromname('processor')
        fillevent.action = datatypes.get_action_fromname('process', fillevent.devicetype)
        fillevent.type = datatypes.get_eventtype_fromname('fixed')
        fillevent.description = event.description
        fillevent.duration = self._continuitylength.total_seconds()
        
        # ...and a video event
        videoevent = PlaylistEntry(parent_node = newevent)
        videoevent.type = datatypes.get_eventtype_fromname('fixed')
        videoevent.description = event.description
        videoevent.trigger = int(event.trigger + self._continuitylength.total_seconds())
        videoevent.device = self._videodevice
        videoevent.devicetype = datatypes.get_devicetype_fromname('Video')
        videoevent.action = datatypes.get_action_fromname('Play', videoevent.devicetype)
        videoevent.eventdata.append(PlaylistData('filename', self._livefilename))
        videoevent.duration = event.duration
        
        # VT Clock event
        clockevent = PlaylistEntry(parent_node = newevent)
        clockevent.type = datatypes.get_eventtype_fromname('fixed')
        clockevent.description = event.description
        clockevent.trigger = int(videoevent.trigger - self._clocklength.total_seconds())
        clockevent.device = self._clockdevice
        clockevent.devicetype = datatypes.get_devicetype_fromname('Video')
        clockevent.action = datatypes.get_action_fromname('Play', clockevent.devicetype)
        clockevent.eventdata.append(PlaylistData('filename', self._clockname))
        clockevent.duration = self._clocklength.total_seconds()
        
        # Construct a manual hold event
        manualevent = PlaylistEntry(parent_node = newevent)
        manualevent.trigger = int(event.trigger + self._continuitylength.total_seconds()) + 1
        manualevent.type = datatypes.get_eventtype_fromname('manual')
        manualevent.description = event.description
        manualevent.duration = event.duration
        manualevent.callback = "Channel::manualHoldRelease"
        
        if (event.duration > self._nownextmin.total_seconds()):
            # Generate CG overlay events
            cgparent = PlaylistEntry(parent_node = manualevent)
            cgparent.device = self._cgdevice
            cgparent.type = datatypes.get_eventtype_fromname('fixed')
            cgparent.devicetype = datatypes.get_devicetype_fromname('CG')
            cgparent.action = datatypes.get_action_fromname('Parent', cgparent.devicetype)
            cgparent.duration = 0
            cgparent.eventdata.append(PlaylistData('hostlayer', self._nownextlayer))
            
            
            runningtrigtime = 0
            if ((videoevent.duration > self._nownextmin.total_seconds()) and 
                (videoevent.duration < self._nownextperiod.total_seconds() * 1.25)):
                runningtrigtime = videoevent.trigger + videoevent.duration / 2
            else:
                runningtrigtime = int(videoevent.trigger + self._nownextperiod.total_seconds())
        
            cgparent.trigger = runningtrigtime
        
            while (runningtrigtime < (videoevent.trigger + videoevent.duration)):
                # Generate progressively later CG events
                cgentry = PlaylistEntry(parent_node = cgparent)
                cgentry.device = self._cgdevice
                cgentry.type = datatypes.get_eventtype_fromname('fixed')
                cgentry.devicetype = datatypes.get_devicetype_fromname('CG')
                cgentry.action = datatypes.get_action_fromname('Add', cgparent.devicetype)
                cgentry.duration = 0
                cgentry.eventdata.append(PlaylistData('hostlayer', self._nownextlayer))
                cgentry.eventdata.append(PlaylistData('graphicname', self._nownextname))
                
                # Set up the labels (next is filled by callback)
                cgentry.eventdata.append(PlaylistData('nexttext', 'ppfill'))
                
                if (event.description != ''):
                    cgentry.eventdata.append(PlaylistData('nowtext', 'Now: {0}'.format(event.description)))
                    
                cgentry.callback = "EventProcessor_Fill::populateCGNowNext"
                
                
                runningtrigtime += int(self._nownextperiod.total_seconds())
                
            # Fix the duration to encompass every child
            cgparent.duration = runningtrigtime - cgparent.trigger
                
        return newevent