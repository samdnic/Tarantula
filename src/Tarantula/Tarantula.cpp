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
*   File Name   : Tarantula.cpp
*   Version     : 1.0
*   Description : Tarantula main file.
*
*****************************************************************************/


#include <iostream>
#include <queue>
#include <ctime>
#include <dirent.h> //for reading the directories
#include <unistd.h>
#include <algorithm>
#include <mutex>

#include "TarantulaPlugin.h" //this is the one place in the core where this is included.
#include "Log_Screen.h"
#include "Channel.h"
#include "Device.h"
#include "TarantulaPluginLoader.h"
#include "BaseConfigLoader.h"
#include "PluginConfigLoader.h"
#include "MouseCatcherCommon.h"
#include "MouseCatcherCore.h"
#include "Misc.h"
#include "AsyncJobSystem.h"
#include <sys/resource.h>

using std::cout;
using std::cerr;
using std::endl;

// Globals
Log g_logger;
std::vector<cbBegunPlaying> g_begunplayingcallbacks;
std::vector<cbEndPlaying> g_endplayingcallbacks;
std::vector<cbTick> g_tickcallbacks;
std::shared_ptr<Channel> g_channel;
std::map<std::string, std::shared_ptr<Device>> g_devices;
std::vector<PluginStateData> g_plugins;
//It doesn't work if I put these elsewhere, plugins unload each other ~SN
std::vector<std::shared_ptr<MouseCatcherSourcePlugin>> g_mcsources;
std::map<std::string, std::shared_ptr<MouseCatcherProcessorPlugin>> g_mcprocessors;
std::shared_ptr<BaseConfigLoader> g_pbaseconfig;
std::shared_ptr<SQLiteDB> g_pcoredatabase;

//! Callback functions to run immediately before an event
std::unordered_map<std::string, PreProcessorHandler> g_preprocessorlist;

DebugData g_dbg;

// Async thread runner system
AsyncJobSystem g_async;

// Mutex for access to Tarantula system core
std::timed_mutex g_core_lock;

// Functions used only in this file
static void processPluginStates ();
static void unloadPlugin (PluginStateData& state, bool attemptreload = false);

int main (int argc, char *argv[])
{
    GlobalStuff *gs = NewGS();

    //Static register the screen log handler if modules fail
    Hook h;
    h.gs = gs;
    Log_Screen ls(h);

    // Load the config
    try
    {
        g_pbaseconfig = std::make_shared<BaseConfigLoader>();
        g_pbaseconfig->LoadConfig("config/Base.xml");
    }
    catch (std::exception& e)
    {
        g_logger.error("Initial startup", std::string("Could not load base config file. Error: ") + e.what());
        g_logger.info("Tarantula Core", "Shutting down...");

	return 1;
    }

    // Load the core database
    // UNHAPPY NOTE: This MUST be run before any plugins try and use SQLite, or weird segfaults result
    g_pcoredatabase = std::make_shared<SQLiteDB>(g_pbaseconfig->getDatabasePath().c_str());

    // Load all non-Mousecatcher plugins
    loadAllPlugins("config/" + g_pbaseconfig->getDevicesPath(), "Device");
    loadAllPlugins("config/" + g_pbaseconfig->getInterfacesPath(), "Interface");
    loadAllPlugins("config/" + g_pbaseconfig->getLogsPath(), "Logger");
    g_logger.info("Tarantula Core",
            "Config loaded. System name is: " + g_pbaseconfig->getSystemName());


    try
    {
        g_channel = std::make_shared<Channel>();

    }
    catch (std::exception&)
    {
        g_logger.info("Initialisation", "Exception caught when creating channel");
    }

    // Initialise MouseCatcher
    MouseCatcherCore::init("config/" + g_pbaseconfig->getEventSourcesPath(),
            "config/" + g_pbaseconfig->getEventProcessorsPath());


    // Tick loop with length set by framerate
    while (1)
    {
        timespec ts;
        clock_gettime(CLOCK_MONOTONIC, &ts);
        timespec begin = ts;

        // Grab core lock
        if (!g_core_lock.try_lock_for(std::chrono::nanoseconds(
                static_cast<int>(1000000000 / g_pbaseconfig->getFramerate()))))
        {
            g_logger.warn("Tarantula Main" + ERROR_LOC, "Unable to grab core mutex lock");
            continue;
        }

        // Run frame tick functions
        try
        {
        	// Channel ticks
        	g_channel->tick();

        	// Devices and plugin states
        	deviceTicks();
        	processPluginStates();

        	// Progress async job state machine
        	g_async.completeAsyncJobs();

            // Run event interface callbacks
        	MouseCatcherCore::eventSourcePluginTicks();
        	MouseCatcherCore::eventQueueTicks();
        }
        catch (...)
        {
            g_logger.warn("Tarantula Main" + ERROR_LOC, "Something went wrong and wasn't handled. This is bad.");
        }

        // Release mutex
        g_core_lock.unlock();

        clock_gettime(CLOCK_MONOTONIC, &ts);
        timespec end = ts;
        clock_t diff = end.tv_nsec - begin.tv_nsec;
        if (diff < 0)
        {
            // We're across seconds
            clock_t sdiff = end.tv_sec - begin.tv_sec;
            diff = sdiff * 1000000000 + end.tv_nsec - begin.tv_nsec;
        }
        clock_t remaining = (1000000000 / g_pbaseconfig->getFramerate()) - diff;
        remaining /= 1000;
        g_dbg.lastTickTimeUsed = (double) diff / 1000000;

        if (remaining < 0)
        {
            g_logger.warn("Tarantula Main" + ERROR_LOC, "That tick took "+ ConvertType::floatToString((double) diff / 1000000)
                    + "ms - Too Long!");
            continue;
        }
        usleep(remaining);
    }
    return 0;
}


/**
 * Unload and reload a crashed plugin
 *
 * @param state         Reference to plugin state variable
 * @param attemptreload Should the reload timer be set if available?
 */
void unloadPlugin (PluginStateData& state, bool attemptreload /* = false */)
{
    // Set the reload timer if enabled
    if (attemptreload && state.reloadsremaining > 0)
    {
        state.reloadtimer = g_pbaseconfig->getPluginReloadTime(state.reloadsremaining);
        state.reloadsremaining--;
    }
    else
    {
        g_logger.error(state.ppluginreference->getPluginName(), "Plugin will be shut down");
        state.reloadtimer = 0;
    }

    // Unload the plugin
    state.ppluginreference->disablePlugin();
}

/**
 * Iterate over all loaded plugins and process the status state machine
 */
void processPluginStates ()
{
    // Process the state machine on all plugins
    for (PluginStateData& pluginstate : g_plugins)
    {
        // If plugin is waiting on reload, handle the counter
        if (pluginstate.reloadtimer > 0)
        {
            // Plugin has unloaded and is waiting for reload timer to expire
            --pluginstate.reloadtimer;

            if (0 == pluginstate.reloadtimer)
            {
                g_logger.info(pluginstate.ppluginreference->getPluginName(),
                        "Reloading plugin after earlier failure");
                std::string file = pluginstate.ppluginreference->getConfigFilename();

                pluginstate.ppluginreference.reset();

                // Reload the plugin
                PluginConfigLoader plugin_config;
                plugin_config.loadConfig(file, pluginstate.type);
                ActivatePlugin(plugin_config.getConfig(), pluginstate.ppluginreference);

                // Set the reload timer to the reload timeout * -1. If we get that many frames without another crash,
                // reloadsremaining will reset
                pluginstate.reloadtimer = g_pbaseconfig->getPluginReloadTime(pluginstate.reloadsremaining + 1) * -1;
            }
        }
        else if (pluginstate.reloadtimer < 0)
        {
            ++pluginstate.reloadtimer;

            if (0 == pluginstate.reloadtimer)
            {
                // Its been long enough without a crash, reset reload
                pluginstate.reloadsremaining = g_pbaseconfig->getPluginReloadCount();
                g_logger.info(pluginstate.ppluginreference->getPluginName(), "Plugin stabilised after reload");
            }
        }

        // Check and handle plugin state
        switch (pluginstate.ppluginreference->getStatus())
        {
            case STARTING:
            {
                g_logger.warn(pluginstate.ppluginreference->getPluginName(),
                        "Plugin still marked as starting.");
                break;
            }
            case FAILED:
            {
                g_logger.error(pluginstate.ppluginreference->getPluginName(),
                        "Unloading plugin after startup failure " +
                        ConvertType::intToString(pluginstate.reloadsremaining) + " reloads remaining");
                unloadPlugin(pluginstate, true);
                break;
            }
            case CRASHED:
            {
                g_logger.error(pluginstate.ppluginreference->getPluginName(),
                        "Unloading plugin due to crash. " + ConvertType::intToString(pluginstate.reloadsremaining) +
                        " reloads remaining");
                unloadPlugin(pluginstate, true);
                break;
            }
            case UNLOAD:
            case READY:
            case WAITING:
            default:
            {
                // Nothing to do here
                break;
            }
        }
    }

    // Delete all plugins that are unloaded
    g_plugins.erase(std::remove_if(g_plugins.begin(), g_plugins.end(),
                    [](PluginStateData p)
                    {
                        return p.ppluginreference->getStatus() == UNLOAD && p.reloadtimer == 0;
                    }), g_plugins.end());

}


