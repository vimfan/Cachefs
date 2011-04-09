#!/bin/bash

PROJECT_ROOT=`dirname $0`

CFLAGS="ble"
PROJECT_ROOT="/home/seba/job/nsn/ssh_cache_fs"
CACHE_FS="$PROJECT_ROOT/stress_test/cachefs"
STD_MOUNTPOINT="${CACHE_FS}/std"
STD_CACHE="${CACHE_FS}/cache_std"
BOOST_MOUNTPOINT="${CACHE_FS}/boost"
BOOST_CACHE="${CACHE_FS}/cache_boost"

cache_size()
{
    echo "CACHE SIZE STD:"
    du -sh $STD_CACHE
    echo "CACHE SIZE BOOST:"
    du -sh $BOOST_CACHE
}

compile ()
{
    make clean > /dev/null 2>&1
    time make CC=g++ spirit.exe # adl.exe
}

compile_with_cflags ()
{
    make clean > /dev/null 2>&1
    CFLAGS="-I${BOOST_CACHE} -I${STD_CACHE} -I${STD_MOUNTPOINT} -I${BOOST_MOUNTPOINT}"
    echo "compiled with flags $CFLAGS"
    #time make CC=g++ CFLAGS="$CFLAGS" spirit.exe adl.exe
    time g++ $CFLAGS spirit.cpp -o spirit.exe
}

testcase ()
{
    testname=$1
    boost=$2
    std=$3
    shift
    shift
    shift
    cflags=$@
    echo "===================================================================="
    echo "Testcase: $testname"
    #echo "Boost dir: $boost"
    #echo "Std dir: $std"
    cmd="ln -snf $boost $PROJECT_ROOT/stress_test/include/boost"
    cmd2="ln -snf $std $PROJECT_ROOT/stress_test/include/std"
    #echo $cmd
    $cmd
    #echo $cmd2
    $cmd2
    echo "Compiling..."
    if [ "${cflags}s" = "s" ] ; then
        compile
    else
        compile_with_cflags $cflags
    fi
    echo "Done."
    cache_size
}

setUp ()
{
    rm -Rf ${STD_CACHE}
    rm -Rf ${BOOST_CACHE}
    mkdir -p ${STD_MOUNTPOINT}
    mkdir -p ${BOOST_MOUNTPOINT}

    python runner.py config_boost
    python runner.py config_std

    echo "Wait for mount..."
    ls ${PROJECT_ROOT}/stress_test/cachefs/* > /dev/null
    echo "System mounted..."
    pushd $PROJECT_ROOT/stress_test/src
}

tearDown()
{
    fusermount -u $STD_MOUNTPOINT
    fusermount -u $BOOST_MOUNTPOINT
    rm -Rf ${STD_CACHE}
    rm -Rf ${BOOST_CACHE}
    rmdir $STD_MOUNTPOINT
    rmdir $BOOST_MOUNTPOINT
    popd
}

setUp

testcase "NORMAL BUILD" "/win/boost/boost_1_45_0" "/usr/include/c++/4.3.2"
testcase "COMBINED" ${BOOST_MOUNTPOINT} ${STD_MOUNTPOINT} $CFLAGS
testcase "COMBINED 2" ${BOOST_MOUNTPOINT} ${STD_MOUNTPOINT} $CFLAGS

tearDown
setUp

testcase "USING SLOW CACHE" ${BOOST_MOUNTPOINT} ${STD_MOUNTPOINT}
testcase "USING SLOW CACHE SECOND TIME" ${BOOST_MOUNTPOINT} ${STD_MOUNTPOINT}
testcase "USING FAST CACHE" ${BOOST_CACHE} ${STD_CACHE}

tearDown
