ID=

all:
	echo "nothing"

tags: *.py
	ctags -R * --language-force=python

tests:
	nosetests -v --with-id $(ID)

#test: *.py
	#python -v -m unittest $(TCP)
