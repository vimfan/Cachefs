TCP=

all:
	echo "nothing"

tags: *.py
	ctags -R *

tests:
	nosetests -v 

test: *.py
	python -v -m unittest $(TCP)
