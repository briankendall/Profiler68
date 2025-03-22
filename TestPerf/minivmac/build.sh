#!/bin/bash

# Normally I use a Mac II based build of Mini vMac, but in this case I'm setting
# it to be a Plus so that we can use it with MacsBug. (MacsBug 6.x doesn't work
# with Mini vMac, and 5.x only works when Mini vMac is emulating a 68000 mac.)

if [ ! -f setup_t ]; then
    clang setup/tool.c -o setup_t
fi

rm -rf MacDev.app
rm -rf MacDev.xcodeproj
rm -rf DerivedData

rm setup.sh

arm64=$(sysctl -ni hw.optional.arm64)

if [[ "$arm64" == 1 ]]; then
    target="mcar"
else
    target="mc64"
fi

./setup_t \
    -t $target \
    -m Plus \
    -hres 512 -vres 342 \
    -depth 0 \
    -mem 4M \
    -magnify 1 \
    -speed a \
    -n MacDev \
    -an MacDev \
    -bg 1 \
    -as 0 \
    -km F1 Escape \
    > ./setup.sh
ret=$?

if [ $ret -ne 0 ]; then
    exit $ret
fi

chmod a+x ./setup.sh
./setup.sh
ret=$?

if [ $ret -ne 0 ]; then
    exit $ret
fi

xcodebuild

exit 0
