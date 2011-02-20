all:
	echo "nothing"

tags: *.py
	ctags -R *

ut:
	nosetests -v
