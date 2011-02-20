#!/bin/bash

# Last argument will be treated as number of second which needs invokation to
# be postponed

array=($@)
index=$(($# - 1)) # index of last element
wait_time=${array[$index]}
sleep $wait_time

# remove last element
unset array[$index]
sshfs ${array[@]:0} # pass all arguments further

# I really hate shell programming!
