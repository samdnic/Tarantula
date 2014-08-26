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
*   File Name   : TarantulaPluginLoader.cpp
*   Version     : 1.0
*   Description : Functions for loading plugins
*
*****************************************************************************/


#define PLUGINLOADER // This is a bit of a special case so needs to announce itself as such.
#include "TarantulaCore.h"
#include "TarantulaPlugin.h"
#include <sstream>
#include <dlfcn.h>
#include "TarantulaPluginLoader.h"

#include "SQLiteDB.h"

/**
 * Initialise a new GlobalStuff struct with the relevant pointers
 *
 * @return New GlobalStuff struct
 */
GlobalStuff* NewGS ()
{
    GlobalStuff* pgs = new GlobalStuff();
    pgs->L = &g_logger;
    pgs->Devices = &g_devices;
    pgs->dbg = &g_dbg;
    pgs->Async = &g_async;
    return pgs;
}

/**
 * Load a plugin from a specified config file
 *
 * @param cfg  Configuration data for the plugin to load
 * @param pref Pointer be used as the plugin reference, filled by the plugin
 * itself
 */
std::shared_ptr<Plugin> ActivatePlugin (PluginConfig cfg, std::shared_ptr<Plugin>& pref)
{
    std::stringstream logmsg; // For assembling log messages

    // Try to open the plugin file
    void* ppluginf = dlopen(("bin/" + cfg.m_library).c_str(), RTLD_LAZY);
    if (!ppluginf)
    {
        std::stringstream logmsg;
        logmsg << "Could not open plugin file " << cfg.m_library << " " << dlerror();
        g_logger.error("Plugin Loader", logmsg.str());
        return NULL;
    }

    void *ppluginhdl = dlsym(ppluginf, "LoadPlugin");
    if (!ppluginhdl)
    {
        logmsg << "Could not get Loadplugin function from SO file. Is it a valid plugin?";
        g_logger.error("Plugin Loader", logmsg.str());
        dlclose(ppluginf);
        return NULL;
    }
    // So by this point we have a handle to the plugin function. Now let's call it.
    LoadPluginFunc plugfunc = (LoadPluginFunc) ppluginhdl;
    Hook h;
    h.gs = NewGS();

    try
    {
        // Load the plugin and call a constructor
        plugfunc(h, cfg, pref);

        if (pref)
        {
            // Call a function to add the plugin to a management list (other than g_plugins)
            pref->addPluginReference(pref);
        }
    }
    catch (std::exception& ex)
    {
        logmsg << "Failed to call startup on plugin " << cfg.m_library << " Error: " << ex.what();
        g_logger.error("Plugin Loader", logmsg.str());
        dlclose(ppluginf);
        return NULL;
    }

    // Now add the plugin load details to the core database
    std::shared_ptr<DBQuery> delete_plugin = g_pcoredatabase->prepare("DELETE FROM plugins WHERE instancename = ?");
    std::shared_ptr<DBQuery> add_plugin_query =
    		g_pcoredatabase->prepare("INSERT INTO plugins (instancename, pluginname, type, status) VALUES (?,?,?,?);");


    delete_plugin->addParam(1, DBParam(cfg.m_instance));
    delete_plugin->bindParams();
    sqlite3_step(delete_plugin->getStmt());

    add_plugin_query->addParam(1, DBParam(cfg.m_instance));
    add_plugin_query->addParam(2, DBParam(cfg.m_name));
    add_plugin_query->addParam(3, DBParam(cfg.m_type));

    if (cfg.m_type.compare("Logger"))
    {
    	add_plugin_query->addParam(4, DBParam("starting"));
    }
    else
    {
    	// Logging plugins don't fit the standard status model
    	add_plugin_query->addParam(4, DBParam("notapplicable"));
    }

    add_plugin_query->bindParams();

    sqlite3_step(add_plugin_query->getStmt());


    return pref;
}
