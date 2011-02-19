all:
	echo "nothing"

tags:
	ctags -R *

ut:
	nosetests
