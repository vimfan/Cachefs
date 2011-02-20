#!/bin/bash

# Last argument will be treated as number of second which needs invokation to
# be postponed

SHELL_PID=$$

function on_die_before_sshfs
{
    kill -SIGHUP ${SHELL_PID}
}

trap 'on_die_before_sshfs' SIGTERM
trap 'on_die_before_sshfs' SIGINT

array=($@)
index=$(($# - 1)) # index of last element
wait_time=${array[$index]}

sleep $wait_time

# remove last element
unset array[$index]
sshfs ${array[@]:0} & # pass all arguments to sshfs
SSHFS_PID=$!
#echo $! > SSHFS_PID

function on_die
{
    kill -SIGHUP ${SSHFS_PID}
}

trap 'on_die' SIGTERM
trap 'on_die' SIGINT

wait
# I really hate shell programming!
