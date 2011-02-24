#TCP=

all:
	echo "nothing"

tags: *.py
	ctags -R * --language-force=python

tests:
	nosetests -v 

#test: *.py
	#python -v -m unittest $(TCP)
