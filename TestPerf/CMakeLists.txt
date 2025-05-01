
cmake_minimum_required(VERSION 3.12)
set(CMAKE_CXX_STANDARD 98)
set(CMAKE_CXX_STANDARD_REQUIRED TRUE)
add_definitions(-DMAC_C -DSHORT_DOUBLE_OK=0)

project(TestPerf C ASM)

# Add your own source files here:

add_application(
    TestPerf
    main.c
    resources.r
    
    ../profiler.c
    ../profilerUtils.s
    
    logging/logging.c
)


target_include_directories(TestPerf PRIVATE ${CMAKE_CURRENT_SOURCE_DIR})
target_include_directories(TestPerf PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/..)
target_include_directories(TestPerf PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/logging)

target_link_libraries(TestPerf "-lm")
target_link_libraries(TestPerf ${CMAKE_CURRENT_SOURCE_DIR}/logging/mini-vmac/libClipOut.a)

set(PROJECT_COMPILE_OPTIONS
    -std=gnu90
    -Wno-stringop-overflow
    -Wno-stringop-overread
    -Werror=declaration-after-statement
    -Werror=pointer-sign
    -Wunused-variable
    -Werror=implicit-function-declaration
    -O0
    -ffunction-sections
    -fno-inline
    # The following are needed for the profiler to work at all:
    -g
    -gdwarf-4
    # The following are needed for stack traces to work:
    -ffixed-a6
    -fno-omit-frame-pointer
)
set_target_properties(TestPerf PROPERTIES COMPILE_OPTIONS "${PROJECT_COMPILE_OPTIONS}")

if(CMAKE_SYSTEM_NAME MATCHES Retro68)
    set_target_properties(TestPerf PROPERTIES LINK_FLAGS "-Wl,-gc-sections -Wl,--mac-single")

else()
    set_target_properties(TestPerf PROPERTIES LINK_FLAGS "-Wl,-gc-sections")
endif()


set(SCRIPTS_DIR ${CMAKE_CURRENT_SOURCE_DIR}/scripts)

# Make sure disk image is unmounted:
add_custom_target(check_command ALL
    COMMAND ${SCRIPTS_DIR}/check-and-reset-disk-image.sh ${PROJECT_NAME}
    COMMENT "Checking disk image lock"
    VERBATIM
)
add_dependencies(${PROJECT_NAME}_APPL check_command)


if(DEFINED MACINTOSH_FTP_STAGING_PATH)
    # Copy built app to FTP staging directory:
    add_custom_command(TARGET ${PROJECT_NAME}_APPL POST_BUILD
        COMMAND ${CMAKE_COMMAND} -E copy "${CMAKE_CURRENT_BINARY_DIR}/${PROJECT_NAME}.bin" "${MACINTOSH_FTP_STAGING_PATH}/${PROJECT_NAME}"
        WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
        COMMENT "Copying built app to staging"
    )
else()
    message("Note: MACINTOSH_FTP_STAGING_PATH not defined, will not copy built app to FTP directory")
endif()


# Define IP address used for UDP-based logging
if(NOT DEFINED MACINTOSH_LOGGING_LOCAL_IP)
    add_definitions(-DNO_UDP_LOGGING)
else()
    if(MACINTOSH_LOGGING_LOCAL_IP STREQUAL "auto")
        # Figure out the local IP address automatically
        # First get the default network interface:
        execute_process(
            COMMAND sh -c "route -n get default | awk '/interface:/ {print $2}'"
            OUTPUT_VARIABLE DEFAULT_IFACE
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
        # Then look up its IP address:
        execute_process(
            COMMAND sh -c "ipconfig getifaddr ${DEFAULT_IFACE}"
            OUTPUT_VARIABLE LOCAL_IP
            OUTPUT_STRIP_TRAILING_WHITESPACE
        )
    else()
        set(LOCAL_IP ${MACINTOSH_LOGGING_LOCAL_IP})
    endif()
    
    string(REPLACE "." ";" IP_COMPONENTS ${LOCAL_IP})
    list(GET IP_COMPONENTS 0 IP_PART1)
    list(GET IP_COMPONENTS 1 IP_PART2)
    list(GET IP_COMPONENTS 2 IP_PART3)
    list(GET IP_COMPONENTS 3 IP_PART4)
    add_definitions(
        -DLOGGING_IP_1=${IP_PART1}
        -DLOGGING_IP_2=${IP_PART2}
        -DLOGGING_IP_3=${IP_PART3}
        -DLOGGING_IP_4=${IP_PART4}
    )
endif()
add_definitions(-DLOGGING_AVAILABLE)

# So we can get at the project name in tasks.json:
file(WRITE "${CMAKE_CURRENT_BINARY_DIR}/ProjectName.txt" "${PROJECT_NAME}")
