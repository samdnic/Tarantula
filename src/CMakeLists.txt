cmake_minimum_required (VERSION 2.8)

project(Tarantula)

# Go find some packages
find_package( Boost REQUIRED COMPONENTS system chrono)
include_directories( ${Boost_INCLUDE_DIRS} )

# Make binaries turn up somewhere useful
SET(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${Tarantula_SOURCE_DIR}/../bin)
SET(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${Tarantula_SOURCE_DIR}/../bin)

# Enable C++11
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=c++11 -pthread")

include_directories(../include)

# Build the static bits
set(SUPPORT_LIB_PREFIX "static_")
include(support_libs_build.cmake)

# Build the main executable
file(GLOB core_SRC "Tarantula/*.cpp")
add_executable(Tarantula ${core_SRC})
target_link_libraries(Tarantula dl)
target_link_libraries(Tarantula rt)
target_link_libraries(Tarantula ${SUPPORT_LIB_PREFIX}Common)
target_link_libraries(Tarantula ${SUPPORT_LIB_PREFIX}libPugiXML)
target_link_libraries(Tarantula ${SUPPORT_LIB_PREFIX}Optional)

# Include all the plugins
add_subdirectory(Plugins)