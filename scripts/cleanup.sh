#!/bin/bash

for mountpoint in `mount | grep -i $PWD | cut -f 3 -d " "`;
do
    echo "unmounting $mountpoint..."
    fusermount -u $mountpoint;
    echo "done."
done

echo "remove sockets"
find . -name '*.sock' | xargs rm -f

echo "remove *.pyc"
find . -name '*.pyc' | xargs rm -f

cmd='rm -Rf tests/test_workspace/'
list=`${cmd} 2>&1 | cut -f4 -d' ' | sed -e "s/[:\\\`\']//g" | xargs echo`
for item in `echo $list`; do  
    echo "unmounting ${item}"
    fusermount -u $item;  
done

$cmd

echo "remove mocks"
rm -f mocks

echo "tests/test_workspace"
rm -Rf tests/test_workspace/
