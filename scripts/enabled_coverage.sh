#!/bin/sh

coverage=`which coverage`
if [ $? -ne 0 ] ; then
    echo "PLEASE INSTALL COVERAGE TOOL (debian-derived: sudo apt-get install python-coverage)"
    exit 1;
fi

# disable debug
cmdline=`echo $@ | sed -e s/--debug//g`
$coverage run --branch -p --omit "*usr*" $cmdline
