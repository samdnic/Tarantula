from importlib import import_module

processorlist = {}

def setup_event_processors():
    """Load all the available event processors and register them"""
    # Load up and parse some XML files
    
    # Work out a list of processors which are on, and load them
    activeprocessors = ['EventProcessorDemo']
    
    for processor in activeprocessors:
        module = import_module("EventProcessors.{0}".format(processor))
        proc = getattr(module, processor)()
        processorlist[processor] = proc

class EventProcessorBase(object):
    """Base class for event processor objects"""
        
    def handleevent(self, event):
        """Override this to actually do the work"""
        raise NotImplementedError