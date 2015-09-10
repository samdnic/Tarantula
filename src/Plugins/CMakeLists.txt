# Force position independence and rebuild support classes
set(CMAKE_POSITION_INDEPENDENT_CODE True)
set(SUPPORT_LIB_PREFIX "pic_")
include(../support_libs_build.cmake)

# libCaspar - CasparCG control library
#REQUIRES BOOST
file(GLOB libCaspar_SRC "${PROJECT_SOURCE_DIR}/libCaspar/Caspar*.cpp")
add_library(${SUPPORT_LIB_PREFIX}libCaspar ${libCaspar_SRC})

# Add all plugins

# CasparCG CG device
add_library(CGDevice_Caspar MODULE CGDevice_Caspar/CGDevice_Caspar.cpp)
target_link_libraries(CGDevice_Caspar ${SUPPORT_LIB_PREFIX}libCaspar)

# Demo CG device
add_library(CGDevice_Demo MODULE CGDevice_Demo/CGDevice_Demo.cpp)

# Demo Crosspoint device
add_library(CrosspointDevice_Demo MODULE CrosspointDevice_Demo/CrosspointDevice_Demo.cpp)

# Hedco Crosspoint device
add_library(CrosspointDevice_Hedco MODULE CrosspointDevice_Hedco/CrosspointDevice_Hedco.cpp)

# Syslog logger
add_library(Log_Syslog MODULE Log_Syslog/Log_Syslog.cpp)

# CasparCG video device
add_library(VideoDevice_Caspar MODULE VideoDevice_Caspar/VideoDevice_Caspar.cpp)
target_link_libraries(VideoDevice_Caspar ${SUPPORT_LIB_PREFIX}libCaspar)

# Demo video device
add_library(VideoDevice_Demo MODULE VideoDevice_Demo/VideoDevice_Demo.cpp)

# PiVT video device
add_library(VideoDevice_PiVT MODULE VideoDevice_PiVT/VideoDevice_PiVT.cpp)
#REQUIRES_BOSST

