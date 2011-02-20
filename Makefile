all:
	echo "nothing"

tags: *.py
	ctags -R *

tests:
	nosetests -v 
