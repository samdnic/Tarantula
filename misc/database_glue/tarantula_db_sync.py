import psycopg2
import sqlite3
import os

# Remote database server settings
db_server = "localhost"
db_port = 5432
db_user = "user"
db_pass = "pass"
db_name = "db"

# Local database files
filler_db = "/opt/Tarantula/datafiles/EventProcessor_Fill/filedata.db"
show_db = "/opt/Tarantula/datafiles/EventProcessor_Fill/lazydata.db"
core_db = "/opt/Tarantula/datafiles/coredata.db"

# Connect to remote database
conn = psycopg2.connect(host=db_server, port=db_port, user=db_user, password=db_pass, database=db_name)

# Read data for the schedule_fill_items table
cur = conn.cursor()

cur.execute("SELECT schedule_fill_items.video_id, extract('epoch' from duration), " 
            "(upper(substring(filename from 9 for (length(filename) - 12)))), filename AS description, "
            "item_type, device "
            "FROM schedule_fill_items "
            "LEFT JOIN video_files ON schedule_fill_items.video_id = video_files.video_id "
            "LEFT JOIN video_file_types ON video_files.video_file_type_name = video_file_types.name "
            "LEFT JOIN videos ON schedule_fill_items.video_id = videos.id "
            "WHERE video_file_types.mode = 'schedule'")
filldata_result = cur.fetchall()

# Read data for the full lazy mode table
cur.execute("SELECT videos.id, (extract('epoch' from duration)) * 25 AS duration, "
    "(upper(substring(filename from 9 for (length(filename) - 12)))) AS filename, "
	"COALESCE(NULLIF(videos.schedule_name, ''),NULLIF(video_boxes.display_name, ''), "
		"NULLIF(video_boxes.name,''),NULLIF(video_boxes.url_name,'')) AS description, "
	"'show' AS typename, 'Show' as devicename "
	"FROM video_files "
	"LEFT JOIN videos ON videos.id = video_files.video_id "
	"LEFT JOIN video_boxes ON videos.video_box_id = video_boxes.id "
	"LEFT JOIN video_file_types ON video_files.video_file_type_name = video_file_types.name "
    "WHERE video_file_types.mode = 'schedule' "
        "AND duration > interval '0 seconds' "
        "AND video_boxes.is_enabled = 'true' "
        "AND videos.is_enabled = 'true' "
        "AND video_files.is_enabled = 'true' "
        "AND schedule_fill_enable = 'true' "
    	"AND video_id NOT IN "
    		"(SELECT video_id FROM schedule_fill_items) "
            "GROUP BY videos.id, filename, duration, created_date, video_boxes.display_name, video_boxes.name, video_boxes.url_name, "
            "videos.display_name, videos.url_name, videos.schedule_name "
	"ORDER BY created_date DESC")

showdata_result = cur.fetchall()

# Release the cursor
cur.close()

# Connect to the SQLite database
conn2 = sqlite3.connect(filler_db)

inscur = conn2.cursor()
inscur.execute("DELETE FROM videos;")
inscur.executemany("INSERT INTO videos (id, duration, filename, description, typename, devicename) VALUES (?, ?, ?, ?, ?, ?);", filldata_result)
inscur.close()
conn2.commit()
conn2.close()

conn2 = sqlite3.connect(show_db)
inscur = conn2.cursor()
inscur.execute("ATTACH '" + core_db + "' AS filelist")
inscur.execute("DELETE FROM videos;")
inscur.executemany("INSERT INTO videos (id, duration, filename, description, typename, devicename) VALUES (?, ?, ?, ?, ?, ?);", showdata_result)
inscur.execute("DELETE FROM videos WHERE id IN \
	(SELECT id FROM videos \
		LEFT OUTER JOIN filelist.[main video server_files] f ON f.filename = videos.filename \
		WHERE f.filename IS NULL)")
inscur.execute("DETACH filelist")
inscur.close()
conn2.commit()
conn2.close()


# Shut down the remote connection
conn.close()
