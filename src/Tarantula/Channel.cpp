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
*   File Name   : Channel.cpp
*   Version     : 1.0
*   Description : Class for running channels and all event handling
*
*****************************************************************************/


#include "Channel.h"
#include "CrosspointDevice.h"
#include "VideoDevice.h"
#include "CGDevice.h"
#include "Misc.h"
#include "Log.h"
#include "MouseCatcherCommon.h"
#include "MouseCatcherCore.h"

//this is here because if it were in core header, it would create a loop.
extern std::shared_ptr<Channel> g_channel;

int end = 0;

/**
 * Constructor.
 */
Channel::Channel () : m_pl()
{
    // Disable manual hold
    m_hold_event = -1;

    // Register the preprocessor
    g_preprocessorlist.emplace("Channel::manualHoldRelease", &Channel::manualHoldRelease);
}


Channel::~Channel ()
{

}

/**
 * Queries events to take place this frame and executes them
 */
void Channel::tick ()
{
    // Update hold flag
    m_hold_event = m_pl.getActiveHold(time(NULL));

    //Pull all the time triggered events at the current time
    std::vector<PlaylistEntry> events = m_pl.getEvents(EVENT_FIXED, (time(NULL)));

    //Execute events on devices
    for (PlaylistEntry thisevent : events)
    {
        // Only run events if the channel is not in hold, or the event is a child of the hold
        if (0 == m_hold_event || thisevent.m_parent == m_hold_event)
        {
            runEvent(thisevent);
        }
        else
        {
            g_logger.info(m_channame + " Runner", std::string("Event ") + std::to_string(thisevent.m_eventid) +
                    std::string(" ignored due to active hold ") + std::to_string(m_hold_event));
        }
    }
}

/**
 * Trigger a manual event and release hold on channel
 *
 * @param id Event ID to trigger
 */
void Channel::manualTrigger (int id)
{
    if (id == m_hold_event)
    {
        m_hold_event = 0;

        PlaylistEntry event;
        m_pl.getEventDetails(id, event);

        // Run the callback function
        if (!event.m_preprocessor.empty())
        {
            if (g_preprocessorlist.count(event.m_preprocessor) > 0)
            {
                g_preprocessorlist[event.m_preprocessor](event, this);
            }
            else
            {
                g_logger.warn("Channel Runner" + ERROR_LOC, "Ignoring invalid PreProcessor " + event.m_preprocessor);
            }
        }

        m_pl.processEvent(id);
    }
    else
    {
        g_logger.warn(m_channame + ERROR_LOC, "Got a manual trigger for an inactive hold, ignoring");
    }
}

/**
 * Runs a specified event.
 *
 * @param event The event to run
 */
void Channel::runEvent (PlaylistEntry& event)
{
    // Run the callback function
    if (!event.m_preprocessor.empty())
    {
        if (g_preprocessorlist.count(event.m_preprocessor) > 0)
        {
            g_preprocessorlist[event.m_preprocessor](event, this);
        }
        else
        {
            g_logger.warn("Channel Runner" + ERROR_LOC, "Ignoring invalid PreProcessor " + event.m_preprocessor);
        }
    }

    if ((0 == g_devices.count(event.m_device)) && (event.m_devicetype != EVENTDEVICE_PROCESSOR))
    {
        g_logger.warn("Channel Runner",
                "Device " + event.m_device + " not found for event ID " + ConvertType::intToString(event.m_eventid));

        // Mark event as processed
        m_pl.processEvent(event.m_eventid);

        return;
    }

    switch (event.m_devicetype)
    {
        case EVENTDEVICE_CROSSPOINT:
        {
            CrosspointDevice::runDeviceEvent(g_devices[event.m_device], event);
            break;
        }
        case EVENTDEVICE_VIDEODEVICE:
        {
            VideoDevice::runDeviceEvent(g_devices[event.m_device], event);
            break;
        }
        case EVENTDEVICE_CGDEVICE:
        {
            CGDevice::runDeviceEvent(g_devices[event.m_device], event);
            break;
        }
        case EVENTDEVICE_PROCESSOR:
            break;
    }

    // Marks event as processed
    m_pl.processEvent(event.m_eventid);
}

int Channel::createEvent (PlaylistEntry *pev)
{
    int ret = m_pl.addEvent(pev);
    return ret;
}


/**
 * Callback function for a LiveShow EP manual trigger. Unfortunately it has to go here as the plugin can't access
 * the SQL database directly.
 */
void Channel::manualHoldRelease (PlaylistEntry &event, Channel *pchannel)
{
    // Erase any remaining children of this event
    std::vector<PlaylistEntry> children = pchannel->m_pl.getChildEvents(event.m_eventid);

    for (PlaylistEntry thischild : children)
    {
        pchannel->m_pl.removeEvent(thischild.m_eventid);
    }

    // Perform the shunt
    time_t starttime = event.m_trigger + static_cast<int>(event.m_duration / g_pbaseconfig->getFramerate());
    int length = time(NULL) - starttime;
    pchannel->m_pl.shunt(starttime, length);

}
