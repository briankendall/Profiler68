#!/bin/sh

proj_name=$1
proj_dir=`dirname $0`/..
disk_image=$proj_dir/build/$proj_name.dsk

if ! test -f $disk_image; then
    exit 0
fi

# If the disk image is still mounted, it'll be locked:
flock -nx $disk_image /bin/sh -c :
ret=$?

if [ $ret -ne 0 ]; then
    RED='\033[0;31m'
    NC='\033[0m' # No Color
    echo ${RED}Disk image is still mounted!${NC}
    exit 1
fi

exit 0
