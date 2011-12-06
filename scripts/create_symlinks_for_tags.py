#!/usr/bin/env python
import sys
import os

target=sys.argv[1]

if not os.path.lexists(target):
    os.makedirs(target)

for path in sys.path:
    if os.getcwd() == path:
        continue
    link_target = path
    unslashified_path = path.replace('/', '_')
    new_entry = os.path.join(target, unslashified_path)
    print(" -> ".join([new_entry, link_target]))
    if os.path.lexists(new_entry):
        os.unlink(new_entry)
    os.symlink(link_target, new_entry)

