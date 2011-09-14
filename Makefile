ID=
COVERAGE_BIN=/usr/bin/coverage

all:
	echo "nothing"

tags: *.py
	ctags -R * --language-force=python

tests:
	nosetests-2.7 -v 
test:
	nosetests-2.7 -v --with-id $(ID)

coverage:
	nosetests-2.7 -v --with-coverage --cover-package=sshcachefs
	$(COVERAGE_BIN) report
	$(COVERAGE_BIN) html

#test: *.py
	#python -v -m unittest $(TCP)
