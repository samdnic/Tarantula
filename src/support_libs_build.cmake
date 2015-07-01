# SQLITE 
file(GLOB sqlite_SRC "${PROJECT_SOURCE_DIR}/sqlite-amalgamation/*.c")
add_library(${SUPPORT_LIB_PREFIX}sqlite_amalgamation ${sqlite_SRC})

# Common libraries - used by all plugins
file(GLOB Common_SRC "${PROJECT_SOURCE_DIR}/Common/*.cpp")
add_library(${SUPPORT_LIB_PREFIX}Common ${Common_SRC})

# Optional libraries - used by few plugins
file(GLOB optional_SRC "${PROJECT_SOURCE_DIR}/Optional/*.cpp")
add_library(${SUPPORT_LIB_PREFIX}Optional ${optional_SRC})
target_link_libraries(${SUPPORT_LIB_PREFIX}Optional ${SUPPORT_LIB_PREFIX}sqlite_amalgamation)

# PugiXML - XML handling library
add_library(${SUPPORT_LIB_PREFIX}libPugiXML "${PROJECT_SOURCE_DIR}/libPugiXML/pugixml.cpp")