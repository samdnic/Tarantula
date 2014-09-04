from EventProcessorBase import EventProcessorBase
from datatypes import PlaylistEntry, PlaylistData


class EventProcessor_Demo(EventProcessorBase):
    def __init__(self, xmltree=None):
        """Required, but not really needed..."""
        pass
        
    def handleevent(self, event):
        """Generate a simple sample event"""
    
        demo_child = PlaylistEntry(parent_node = event)
        
        demo_child.duration = 223
        #TODO replace with lookup by name
        demo_child.action = 0
        demo_child.device = "Demo Video Device 1"
        #TODO replace with lookup by device
        demo_child.devicetype = 1
        demo_child.trigger = event.trigger
        demo_child.callback = "EventProcessor_Demo::demoPreProcessor"
        demo_child.description = "Demonstration child event from EP"
        demo_child.type = 0
        
        data = PlaylistData(key = "filename", value = "test1")
        demo_child.eventdata.append(data)
    
        # Using parent_node in the child declaration eliminates need for adding child
        return event