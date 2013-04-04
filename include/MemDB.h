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
*   File Name   : MemDB.h
*   Version     : 1.0
*   Description : Base class for an in-memory SQLite database. A wrapper around
*                 the sqlite functions to make them a bit more C++y Also
*                 contains classes for DBParam and DBQuery used by MemDB.
*
*****************************************************************************/


#pragma once

//a bit of windows debug code to track memory
#ifdef WIN32
#ifdef _DEBUG
#define _CRTDBG_MAP_ALLOC
#include <stdlib.h>
#include <crtdbg.h>
#endif
#endif

#include <string>
#include <map>
#include <vector>
#include "../src/sqlite-amalgamation/sqlite3.h"


#define sqlite3_column_text (const char*)sqlite3_column_text
#define TXT(a) a

enum DBParamType
{
    DBPARAM_INT, DBPARAM_LONG, DBPARAM_STRING, DBPARAM_NULL, DBPARAM_DOUBLE,
};

/**
 * Class to encapsulate multiple types of parameter.
 */
class DBParam
{
public:
    DBParam (int val);
    DBParam (long long val);
    DBParam (std::string val);
    DBParam (double val);
    DBParam ();
    DBParamType m_type;
    int m_intval;
    long long m_longval;
    std::string m_stringval;
    double m_doubleval;
};

/**
 * Provides an interface to store and handle parameterised SQL queries.
 */
class DBQuery
{
public:
    DBQuery ();
    ~DBQuery ();
    void sql (std::string sql, sqlite3 *db);
    void addParam (const int pos, DBParam param);
    void rmParams (); // Clears all params
    void bindParams (); // Binds params to query
    sqlite3_stmt* getStmt (); // Get prepared query for stepping
private:
    std::map<int, DBParam> m_params;
    sqlite3_stmt* m_pstmt;
};

/**
 * Wrapper around SQLite to be more C++
 */
class MemDB
{
public:
    MemDB ();
    MemDB (const char* filename);
    ~MemDB ();
    void dump (const char* filename); // Dumps out the database to an SQLite file
protected:
    DBQuery* prepare (std::string sql);
    void remove (std::string sql);
    void oneTimeExec (std::string sql); // Run a query verbatim without parameters
    int getLastRowID ();
private:
    std::map<std::string, DBQuery> m_queries;
    sqlite3 *m_pdb;
};
