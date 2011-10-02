#!/bin/bash

find . -name '*.sock' | xargs rm
find . -name '*.pyc' | xargs rm

cmd='rm -Rf tests/test_workspace/'
list=`${cmd} 2>&1 | cut -f4 -d' ' | sed -e "s/[:\\\`\']//g" | xargs echo`
for item in `echo $list`; do  
    echo "unmounting ${item}"
    fusermount -u $item;  
done

$cmd
