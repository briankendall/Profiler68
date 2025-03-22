#!/bin/sh

build_dir=$1

if [ -z "$build_dir" ]; then
    echo "Error: didn't get build directory"
    exit 1
fi

project_name=$(cat $build_dir/projectName.txt)

if [ -z "$project_name" ]; then
    echo "Error: didn't get project name"
    exit 1
fi

# Change this to change Mini vMac's speed when running the app
# speed 0 = 1x
# speed 1 = 1.3x (a custom speed meant to try and match a 16 Mhz 68030)
# speed 2 = 2x
# speed 3 = 4x
# speed 4 = 8x
# speed 5 = 16x
# Note: these speeds only apply to this custom build of Mini vMac.
speed=1

project_dir=$(realpath `dirname $0`/..)
minivmac_dir=$project_dir/minivmac

disk_image=$build_dir/$project_name.dsk
named_pipe=$build_dir/app_out
signal_dir=$minivmac_dir/signals

mkdir -p $signal_dir
# These signal files are created so that we can catch when certain events happen
# in the emulated system.
# Our customized Mini vMac will create this file when it receives MSG:quit from
# the emulated system:
finished_signal_file="$signal_dir/closed.txt"
# and will create this file when it receives MSG:boot from the emulated system:
booted_signal_file="$signal_dir/booted.txt"

# All output from Mini vMac is piped into this named pipe, so that other
# processes can get at it (namely display-output.py)
if [ ! -p $named_pipe ]; then
	echo Creating named pipe
	mkfifo $named_pipe
fi

rm -f $booted_signal_file
rm -f $finished_signal_file

# Copy the included system disk image in if it's not already there. In case the
# image ever becomes corrupted, you can just copy system.dsk back into the
# Mini vMac directory again.
if [ ! -f $minivmac_dir/disk1.dsk ]; then
    cp $minivmac_dir/disks/system.dsk $minivmac_dir/disk1.dsk
fi

# If Mini vMac is not already running, launch it:
ps auxc | grep MacDev > /dev/null
ret=$?

if [ $ret -ne 0 ]; then
	echo Launching Mini vMac...
    open --stdout $named_pipe $minivmac_dir/MacDev.app --args $speed
    
    # Wait until it's booted all the way up:
	while [ ! -f "$booted_signal_file" ]; do
		sleep 0.15
	done
	
	rm -f $booted_signal_file
	sleep 0.5
fi


# Mount the disk if needed
flock -nx $disk_image /bin/sh -c :
disk_mounted=$?

if [ $disk_mounted -eq 0 ]; then
    echo Mounting disk
	open "$disk_image" -a "$minivmac_dir/MacDev.app"
else
	echo Note: disk already mounted!
fi

# Wait up to 1.5 seconds for the disk to be mounted, just in case its an invalid
# image and it fails to mount
sleep 0.25

startTime=$(($(gdate +%s%N)/1000000))
while true; do
	flock -nx $disk_image /bin/sh -c :
	disk_mounted=$?
	if [ $disk_mounted -eq 1 ]; then
		break
	fi
	
    currentTime=$(($(gdate +%s%N)/1000000))
	dt=$(( currentTime - startTime ))
    if [ $dt -gt 1250 ]; then
		echo break
		break;
	fi
  
	sleep 0.1
done

if [ $disk_mounted -eq 0 ]; then
	echo Disk never mounted!
	exit 1
fi

echo "---------- start ---------\n\n" > $named_pipe

# Now we send Command+Option+Shift+R into Mini vMac using AppleScript, which
# KeyQuencer should catch and run the application:
osascript << EOF
tell application "MacDev" to activate

tell application "System Events"
	repeat while value of attribute "AXFrontmost" of process "MacDev" = false
		delay 0.1
	end repeat
	delay 0.1
	keystroke "r" using {command down, option down, shift down}
end tell
EOF

# Wait for the app to quit:
while true; do
	if [ -f "$finished_signal_file" ]; then
		break
	fi
	
	if ! pgrep -x "MacDev" > /dev/null; then
		echo "Mini vMac has terminated"
		break
	fi
	
	sleep 0.15
done

rm -f $finished_signal_file

# Hide Mini vMac:
if pgrep -x "MacDev" > /dev/null; then
	osascript -e 'tell application "System Events" to set visible of process "MacDev" to false'
fi

printf "\n----------- end ----------\n" > $named_pipe

exit 0
