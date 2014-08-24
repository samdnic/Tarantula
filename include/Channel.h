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
*   File Name   : Channel.h
*   Version     : 1.0
*   Description : Class for running channels and all event handling
*
*****************************************************************************/


#pragma once

#include <string>
#include <iostream>
#include <functional>
#include <mutex>

#include "TarantulaCore.h"
#include "PlaylistDB.h"

/**
 * Channel class.
 * All the magic of channels to broadcast
 */
class Channel
{
public:
    Channel ();
    ~Channel ();
    void tick ();

    int createEvent (PlaylistEntry *ev);

    void manualTrigger (int id);

    PlaylistDB m_pl;
    std::string m_channame;
    //! Crosspoint name for this channel
    std::string m_xpdevicename;
    //! Crosspoint port name for this channel
    std::string m_xpport;

    static void manualHoldRelease (PlaylistEntry &event, Channel *pchannel);

private:
    void runEvent (PlaylistEntry& pevent);

    void periodicDatabaseSync (std::shared_ptr<void> data, std::timed_mutex &core_lock);

    int m_sync_counter;

    int m_hold_event;
};


extern std::shared_ptr<Channel> g_channel; //declared here because adding it to TarantulaCore creates reference loops.

