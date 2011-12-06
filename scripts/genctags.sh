#!/bin/bash

SCRIPTS_DIR=scripts
FILES_TO_INDEX_TMP_FILE=source_list
INTERFACES_DIR=interfaces

create_interfaces_dir() 
{
    echo "Creating $INTERFACES_DIR directory..."
    mkdir -p $INTERFACES_DIR
}

create_symlinks()
{
    echo "Creating symlinks..."
    $SCRIPTS_DIR/create_symlinks_for_tags.py interfaces
}

create_file_list()
{
    echo "Searching for files..."
    find -L . -name "*.py" > $FILES_TO_INDEX_TMP_FILE
}

delete_file_list()
{
    rm -f $FILES_TO_INDEX_TMP_FILE
}

generate_ctags()
{
    num_of_files=`wc -l ${FILES_TO_INDEX_TMP_FILE}`
    echo "Generating tags... number of files: ${num_of_files}"
    ctags -L $FILES_TO_INDEX_TMP_FILE --language-force=python
}

create_interfaces_dir
create_symlinks
create_file_list
generate_ctags
delete_file_list
