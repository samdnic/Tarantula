from importlib import import_module
import xml.etree.ElementTree as XMLTree
import glob
import os

processorlist = {}

def setup_event_processors(configpath):
    """Load all the available event processors and register them"""
    # Load up and parse some XML files
    confpath = os.path.join('config', configpath, "*.xml")
    for filename in glob.glob(confpath):
        configroot = XMLTree.parse(filename).getroot()
        configdata = configroot.find('PluginLoad')
        
        if configdata.find('Enabled').text.lower() == 'true':
            # Perform some basic validation steps on the config file
            if configdata.find('Type').text != 'EventProcessor':
                print "Config file {0} was a bad type {1}".format(filename, configdata.find('Type').text)
                continue
                
            processorname = configdata.find('Instance').text
            scriptname = configdata.find('ScriptName').text
            
            if not processorname or not scriptname:
                print "Got a blank for Instance or ScriptName in {0}".format(filename)
                
            module = import_module("EventProcessors.{0}".format(scriptname))
            proc = getattr(module, scriptname)(configroot.find('PluginData'))
            processorlist[processorname] = proc
        
        else:
            print "Got a bad file or disabled plugin for {0}".format(filename)

class EventProcessorBase(object):
    """Base class for event processor objects"""
        
    def handleevent(self, event):
        """Override this to actually do the work"""
        raise NotImplementedError