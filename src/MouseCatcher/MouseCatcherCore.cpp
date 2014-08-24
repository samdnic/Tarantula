/******************************************************************************
*   Copyright (C) 2011 - 2013  York Student Television
*
*   Tarantula is free software: you can redistribute it and/or modify
*   it under the terms of the GNU General Public License as published by
*   the Free Software Foundation, either version 3 of the License, or
*   (at your option) any later version.
*
*   Tarantula is distributed in the hope that it will be useful,
*   but WITHOUT ANY WARRANTY; without even the implied warranty of
*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
*   GNU General Public License for more details.
*
*   You should have received a copy of the GNU General Public License
*   along with Tarantula.  If not, see <http://www.gnu.org/licenses/>.
*
*   Contact     : tarantula@ystv.co.uk
*
*   File Name   : MouseCatcherCore.cpp
*   Version     : 1.0
*   Description : The central functions for MouseCatcher
*
*****************************************************************************/


#include <dirent.h> //for reading the directories
#include <vector>
#include <algorithm>

#include "MouseCatcherCommon.h"
#include "MouseCatcherCore.h"
#include "TarantulaPlugin.h"
#include "TarantulaPluginLoader.h"
#include "PluginConfigLoader.h"
#include "PlaylistDB.h"
#include "Misc.h"
#include "VideoDevice.h"
#include "CGDevice.h"

extern std::vector<std::shared_ptr<MouseCatcherSourcePlugin>> g_mcsources;
extern std::map<std::string, std::shared_ptr<MouseCatcherProcessorPlugin>> g_mcprocessors;

namespace MouseCatcherCore
{
    std::vector<EventAction> *g_pactionqueue;

    /**
     * Encapsulates loading plugins, registering callbacks and logging activation
     *
     * @param sourcepath    Path to EventSource plugins
     * @param processorpath Path to EventProcessor plugins
     */
    void init (std::string sourcepath, std::string processorpath)
    {
        g_pactionqueue = new std::vector<EventAction>;
        g_logger.info("MouseCatcherCore", "Now initialising MouseCatcher core");
        loadAllPlugins(sourcepath, "EventSource");
        loadAllPlugins(processorpath, "EventProcessor");
    }

    /**
     * Calls tick() handlers for all the EventProcessor plugins
     */
    void eventSourcePluginTicks ()
    {
        for (std::shared_ptr<MouseCatcherSourcePlugin> thisplugin : g_mcsources)
        {
            if (thisplugin)
            {
                thisplugin->tick(g_pactionqueue);
            }
        }

        // Delete all plugins that are unloaded
        g_mcsources.erase(std::remove_if(g_mcsources.begin(), g_mcsources.end(),
                        [](std::shared_ptr<MouseCatcherSourcePlugin> d){return d->getStatus() == UNLOAD;}),
                        g_mcsources.end());
    }

    /**
     * Process an individual incoming event
     *
     * @param thisevent MouseCatcherEvent
     * @param lastid int The id of the last inserted event, -1 for none
     * @param ischild bool
     * @return int The id of the inserted event for relative tails
     */
    int processEvent (MouseCatcherEvent event, int lastid, bool ischild,
            EventAction& action)
    {
        if (event.m_extradata.count("duration") > 0)
		{
			try
			{
				event.m_duration = 0;
				int lastfind = 0;
				int i = 0;
				size_t found;

				do
				{
					found = event.m_extradata["duration"].find(':', lastfind);
					if (std::string::npos == found)
					{
						found = event.m_extradata["duration"].length();
					}

					std::string sub = event.m_extradata["duration"].substr(lastfind, found - lastfind);
					lastfind = found + 1;

					event.m_duration = event.m_duration * 60 +
							ConvertType::stringToInt(sub);
					i++;
				}
				while (found != event.m_extradata["duration"].length() && i < 3);
			}
			catch (std::exception &ex)
			{
				g_logger.warn("MouseCatcherCore " + ERROR_LOC, "Bad duration of " + event.m_extradata["duration"] +
						" selecting 10s instead");
				event.m_duration = 10;
			}

			// Convert duration from seconds to frames
			event.m_duration *= g_pbaseconfig->getFramerate();

			event.m_extradata.erase("duration");
		}

        // Process event through EventProcessors, then run this function on new events (ignore "special" manual events)
        if (0 == g_devices.count(event.m_targetdevice) && EVENT_MANUAL != event.m_eventtype)
        {
            g_logger.info("MouseCatcherCore", "Scanning Event Processors");

            // Run an EventProcessor
            if (1 == g_mcprocessors.count(event.m_targetdevice))
            {
                // Create a variable to hold original event
                MouseCatcherEvent originalevent = event;

                // Action fields do not apply to processors, set it to -1
                originalevent.m_action = -1;

                g_mcprocessors[event.m_targetdevice]->handleEvent(originalevent, event);
            }
            else
            {
                g_logger.warn("MouseCatcherCore", "Got event for bad device: " + event.m_targetdevice);

                // Return failure code
                action.returnmessage = "Device/Processor " + event.m_targetdevice + " not found!";
                return -1;
            }
        }
        else
        {
            // Check that we got a working event chain
            if ((lastid < 0) && (event.m_eventtype != EVENT_FIXED))
            {
                g_logger.warn("MouseCatcherCore", "An invalid event chain was detected");
                return -1;
            }
        }

        // Create and add a playlist event for the parent
        PlaylistEntry playlistevent;
        convertToPlaylistEvent(&event, lastid, &playlistevent);

        int eventid = g_channel->createEvent(&playlistevent);

        // Loop over and handle children
        for (MouseCatcherEvent thischild : event.m_childevents)
        {
            // Inherit parent descriptions
            if (thischild.m_description.empty())
            {
                thischild.m_description = event.m_description;
            }

            processEvent(thischild, eventid, true, action);
        }

        return eventid;

    }

    /**
     * Gets all events the system knows about within a range of time
     *
     * @param starttime     Only fetch events scheduled after this timestamp.
     * @param length		Length of range to fetch events for
     * @param eventvector   Vector to insert the events into.
     * @param action        Should we grab current or next events?
     * @return              False if given channel was invalid, otherwise true.
     */
    void getEvents (time_t starttime, int length, std::vector<MouseCatcherEvent>& eventvector,
    		std::string action)
    {
        std::vector<PlaylistEntry> playlistevents;

		if (!action.compare("current"))
		{
			playlistevents = g_channel->m_pl.getExecutingEvents();
		}
		else if (!action.compare("next"))
		{
			try
			{
				playlistevents.push_back(g_channel->m_pl.getNextEvent());
			}
			catch (std::exception&)
			{
				// Nothing found, not an error.
			}
		}
		else
		{
			playlistevents = g_channel->m_pl.getEventList(starttime, length);
		}

		for (std::vector<PlaylistEntry>::iterator it2 =
				playlistevents.begin(); it2 != playlistevents.end(); ++it2)
		{
			std::vector<PlaylistEntry> playlistchildren = g_channel->m_pl.getChildEvents(it2->m_eventid);

			MouseCatcherEvent tempevent;
			MouseCatcherCore::convertToMCEvent(it2.base(), &tempevent, &g_logger);
			eventvector.push_back(tempevent);
		}
	}

    /**
     * Remove an event from the playlist
     *
     * @param action EventAction containing data for this event
     */
    void removeEvent (EventAction& action)
    {
        g_channel->m_pl.removeEvent(action.eventid);

    }

    /**
     * Erase a playlist event and create a new one in its place
     * @param action EventAction containing data for this event
     */
    void editEvent (EventAction& action)
    {
        removeEvent(action);

        if (!action.returnmessage.compare("Deleted successfully"))
        {
            processEvent(action.event, -1, false, action);
        }
        else
        {
            action.returnmessage = "Unable to locate event to edit";
        }

    }

    /**
     * Push a set of playlist events out by a set amount of time
     * @param action EventAction with some data. m_triggertime becomes shunt start, and m_duration becomes length
     */
    void shuntEvents (EventAction& action)
    {
        g_channel->m_pl.shunt(action.event.m_triggertime, action.event.m_duration);
    }

    /**
     * End a manual playlist hold and run the next events
     *
     * @param action EventAction with some data. Only the channel is used
     */
    void triggerEvent (EventAction &action)
    {
        g_channel->manualTrigger(action.eventid);
    }


    /**
     * Rerun the EventProcessors that created an event
     *
     * @param action EventAction with some data. Channel and eventid used
     */
    void regenerateEvent (EventAction &action)
    {
        // Get this event from the playlist
        PlaylistEntry currentevent;
        g_channel->m_pl.getEventDetails(action.eventid, currentevent);

        // Check that event was actually an EventProcessor, there's no point running this on anything else
        if (EVENTDEVICE_PROCESSOR != currentevent.m_devicetype)
        {
            action.returnmessage = "Attempted to regenerate a non-processor event";
            g_logger.info("Event Queue" + ERROR_LOC, action.returnmessage);
            return;
        }

        MouseCatcherEvent currentMCevent;
        if (!convertToMCEvent(&currentevent, &currentMCevent, &g_logger))
        {
            action.returnmessage = "Unable to convert event for regeneration";
            g_logger.info("Event Queue" + ERROR_LOC, action.returnmessage);
            return;
        }

        // Delete the existing playlist event
        g_channel->m_pl.removeEvent(action.eventid);

        // Clean up the existing event
        currentMCevent.m_childevents.clear();

        // Generate a fresh one
        processEvent(currentMCevent, -1, false, action);
    }

    /**
     * Pull a list of playlist events.
     * Selects all events between m_triggertime and m_triggertime + m_duration,
     * and provides them to the EventSource using the updatePlaylist callback.
     *
     * Optionally allows for getting current or next event
     *
     * @param action EventAction containing data for this event
     */
    void updateEvents (EventAction& action)
    {
        std::vector<MouseCatcherEvent> eventdata;

        getEvents(action.event.m_triggertime,
        		action.event.m_duration, eventdata, action.event.m_action_name);

        action.thisplugin->updatePlaylist(eventdata, action.additionaldata);
    }

    /**
     * Gets a list of devices loaded into the system and provides it to the
     * updateDevices() callback.
     *
     * @param action EventAction containing data for this event
     */
    void getLoadedDevices (EventAction& action)
    {
        std::map<std::string, std::string> devices;
        for(std::pair<std::string, std::shared_ptr<Device>> currentdevice :  g_devices)
        {
            devices[currentdevice.first] =
                    playlist_device_type_vector.at(currentdevice.second->getType());
        }

        action.thisplugin->updateDevices(devices, action.additionaldata);
    }

    /**
     * Gets a list of actions for a specified device, and passes it to the
     * updateDeviceActions callback.
     *
     * @param action EventAction containing data for this event
     */
    void getTypeActions (EventAction& action)
    {
        std::vector<ActionInformation> typeactions;
        if (1 == g_devices.count(action.event.m_targetdevice))
        {
            for (const ActionInformation *pactiondata : *(g_devices[action.event.m_targetdevice]->m_actionlist))
            {
                typeactions.push_back(*pactiondata);
            }

            action.thisplugin->updateDeviceActions(action.event.m_targetdevice,
                    typeactions, action.additionaldata);
        }
        else
        {
            g_logger.warn("GetTypeActions", "Unable to get actions for nonexistent device " + action.event.m_targetdevice);
            action.returnmessage = "Unable to get actions for nonexistent device " + action.event.m_targetdevice;
        }
    }

    /**
     * Get a list of all files on a device
     *
     * @param action
     */
    void getDeviceFiles (EventAction& action)
    {
        if (1 == g_devices.count(action.event.m_targetdevice))
        {
        	std::vector<std::pair<std::string, int>> files;

            if (EVENTDEVICE_VIDEODEVICE == g_devices[action.event.m_targetdevice]->getType())
            {
                std::shared_ptr<VideoDevice> dev =
                        std::static_pointer_cast<VideoDevice>(g_devices[action.event.m_targetdevice]);
                dev->getFileList(files);
            }
            else if (EVENTDEVICE_CGDEVICE == g_devices[action.event.m_targetdevice]->getType())
            {
                std::shared_ptr<CGDevice> dev =
                        std::static_pointer_cast<CGDevice>(g_devices[action.event.m_targetdevice]);
                dev->getTemplateList(files);
            }
            else
            {
                g_logger.warn("GetTypeActions", "Unable to get files for invalid device " + action.event.m_targetdevice);
                action.returnmessage = "Unable to get files for invalid device " + action.event.m_targetdevice;
                return;
            }
            action.thisplugin->updateFiles(action.event.m_targetdevice, files,
            		action.additionaldata);
        }
        else
        {
            g_logger.warn("GetTypeActions", "Unable to get files for nonexistent device " + action.event.m_targetdevice);
            action.returnmessage = "Unable to get files for nonexistent device " + action.event.m_targetdevice;
        }
    }

    /**
     * Gets a list of eventprocessors.
     *
     * @param action EventAction containing data for this event
     */
    void getEventProcessors (EventAction& action)
    {
        std::map<std::string, ProcessorInformation> processors;

        for (std::pair<std::string, std::shared_ptr<MouseCatcherProcessorPlugin>> thisprocessor : g_mcprocessors)
        {
            if (UNLOAD != thisprocessor.second->getStatus())
            {
                processors[thisprocessor.first] = thisprocessor.second->getProcessorInformation();
            }
            else
            {
                g_mcprocessors.erase(thisprocessor.first);
            }
        }

        action.thisplugin->updateEventProcessors(processors, action.additionaldata);
    }

    /**
     * Converts and sets up new events from an EventSource, running EventProcessors.
     */
    void eventQueueTicks ()
    {
        for (EventAction& thisaction : *g_pactionqueue)
        {
            EventAction* p_action = &thisaction;

            if (p_action->isprocessed != true)
            {
                try
                {
                    switch (thisaction.action)
                    {
                        case ACTION_ADD:
                        {
                            thisaction.eventid = processEvent(thisaction.event, -1, false, *p_action);
                        }
                        break;
                        case ACTION_REMOVE:
                        {
                            removeEvent(thisaction);
                        }
                        break;
                        case ACTION_EDIT:
                        {
                            editEvent(thisaction);
                        }
                        break;
                        case ACTION_SHUNT:
                        {
                            shuntEvents(thisaction);
                        }
                        break;
                        case ACTION_TRIGGER:
                        {
                            triggerEvent(thisaction);
                        }
                        break;
                        case ACTION_REGENERATE:
                        {
                            regenerateEvent(thisaction);
                        }
                        break;
                        case ACTION_UPDATE_PLAYLIST:
                        {
                            if (thisaction.thisplugin)
                            {
                                updateEvents(thisaction);
                            }
                        }
                        break;
                        case ACTION_UPDATE_DEVICES:
                        {
                            if (thisaction.thisplugin)
                            {
                                getLoadedDevices(thisaction);
                            }
                        }
                        break;
                        case ACTION_UPDATE_ACTIONS:
                        {
                            if (thisaction.thisplugin)
                            {
                                getTypeActions(thisaction);
                            }
                        }
                        break;
                        case ACTION_UPDATE_PROCESSORS:
                        {
                            if (thisaction.thisplugin)
                            {
                                getEventProcessors(thisaction);
                            }
                        }
                        break;
                        case ACTION_UPDATE_FILES:
                        {
                        	if (thisaction.thisplugin)
                        	{
                        		getDeviceFiles(thisaction);
                        	}
                        }
                        break;
                        default:
                        {
                            throw std::exception();
                        }
                        break;
                    }
                }
                catch (std::exception&)
                {
                    g_logger.warn("MouseCatcherCore::eventQueueTicks " + ERROR_LOC,
                    		"Unknown Action returned from g_pactionqueue. Action: " + std::to_string(thisaction.action));
                    thisaction.returnmessage = "Unknown Action type found";
                }
                thisaction.isprocessed = true;
            }
        }
    }

    /**
     * Converts a PlaylistEntry to a MouseCatcher event.
     *
     * @param pplaylistevent  The event to convert.
     * @param pgeneratedevent Pointer to a MouseCatcherEvent for output
     * @param plog            Pointer to global logging instance
     * @return                True on success, false on failure
     */
    bool convertToMCEvent (PlaylistEntry *pplaylistevent, MouseCatcherEvent *pgeneratedevent, Log *plog)
    {
        try
        {
            pgeneratedevent->m_targetdevice = pplaylistevent->m_device;
            pgeneratedevent->m_duration = pplaylistevent->m_duration;
            pgeneratedevent->m_eventtype = pplaylistevent->m_eventtype;
            pgeneratedevent->m_triggertime = pplaylistevent->m_trigger;
            pgeneratedevent->m_action = pplaylistevent->m_action;
            pgeneratedevent->m_extradata = pplaylistevent->m_extras;
            pgeneratedevent->m_eventid = pplaylistevent->m_eventid;
            pgeneratedevent->m_preprocessor = pplaylistevent->m_preprocessor;
            pgeneratedevent->m_description = pplaylistevent->m_description;

            if (EVENT_MANUAL != pplaylistevent->m_eventtype)
            {
                // Check the device/processor is real and remains active
                if ((0 == g_devices.count(pgeneratedevent->m_targetdevice)) &&
                        (0 == g_mcprocessors.count(pgeneratedevent->m_targetdevice)))
                {
                    g_logger.warn("convertToMCEvent", "Got event for non-existent or unloaded device or processor: " +
                            pgeneratedevent->m_targetdevice);
                    throw std::exception();
                }

                // Get an action name if not an EP
                if (pgeneratedevent->m_action > -1)
                {
                    try
                    {
                        pgeneratedevent->m_action_name = g_devices[pgeneratedevent->m_targetdevice]->m_actionlist->
                                at(pgeneratedevent->m_action)->name;
                    }
                    catch (std::exception &ex)
                    {
                        g_logger.warn("convertToMCEvent", "Unable to locate action with index " +
                                ConvertType::intToString(pgeneratedevent->m_action) + " on device " +
                                pgeneratedevent->m_targetdevice);
                    }

                }
            }

            // Recursively grab child events
            std::vector<PlaylistEntry> eventchildren =
                    g_channel->m_pl.getChildEvents(pplaylistevent->m_eventid);

            for (PlaylistEntry thischild : eventchildren)
            {
                MouseCatcherEvent tempchild;
                MouseCatcherCore::convertToMCEvent(&thischild, &tempchild, plog);

                pgeneratedevent->m_childevents.push_back(tempchild);
            }
        }
        catch (...)
        {
            plog->error("convert_to_mc_event", "Failed to convert event " +
                    ConvertType::intToString(pplaylistevent->m_eventid) +
                    " to MouseCatcher event");
            return false;
        }

        return true;
    }

    /**
     * Convert a MouseCatcher event to a playlist event
     * @param pmcevent       Pointer to the event to convert
     * @param parentid       ID of the parent event if this is a child, -1 otherwise
     * @param pplaylistevent A pointer to a PlaylistEntry for output
     *
     * @return               True on success, false on failure.
     */
    bool convertToPlaylistEvent (MouseCatcherEvent *pmcevent, int parentid,
            PlaylistEntry *pplaylistevent)
    {
        if (1 == g_devices.count(pmcevent->m_targetdevice) && EVENT_MANUAL != pmcevent->m_eventtype)
        {
            pplaylistevent->m_devicetype = g_devices[pmcevent->m_targetdevice]->getType();

            if (-1 == pmcevent->m_action)
            {
                // Lookup the action ID from the list
                for (const ActionInformation *thisaction : *(g_devices[pmcevent->m_targetdevice]->m_actionlist))
                {
                    if (!thisaction->name.compare(pmcevent->m_action_name))
                    {
                        pmcevent->m_action = thisaction->actionid;
                        break;
                    }
                }

                // Check we got an ID number
                if (-1 == pmcevent->m_action)
                {
                    g_logger.warn("convertToPlaylistEvent", "Unable to convert as action " + pmcevent->m_action_name +
                            " does not exist on device " + pmcevent->m_targetdevice);
                    return false;
                }
            }
        }
        else if (EVENT_MANUAL != pmcevent->m_eventtype)
        {
            if (1 == g_mcprocessors.count(pmcevent->m_targetdevice))
            {
                pplaylistevent->m_devicetype = EVENTDEVICE_PROCESSOR;
            }
            else
            {
                g_logger.warn("convertToPlaylistEvent",
                        "Unable to convert as device " + pmcevent->m_targetdevice + " does not exist.");
                return false;
            }
        }

        pplaylistevent->m_device = pmcevent->m_targetdevice;
        pplaylistevent->m_duration = pmcevent->m_duration;
        pplaylistevent->m_trigger = pmcevent->m_triggertime;
        pplaylistevent->m_action = pmcevent->m_action;
        pplaylistevent->m_extras = pmcevent->m_extradata;
        pplaylistevent->m_preprocessor = pmcevent->m_preprocessor;
        pplaylistevent->m_description = pmcevent->m_description;

        if (parentid > -1)
        {
            pplaylistevent->m_parent = parentid;
        }

        pplaylistevent->m_eventtype = pmcevent->m_eventtype;

        return true;
    }

}

