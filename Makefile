ID=
COVERAGE_BIN=/usr/bin/coverage

all:
	echo "nothing"

tags: *.py
	ctags -R * --language-force=python

tests:
	nosetests -v --with-id $(ID)

coverage:
	nosetests -v --with-coverage --cover-package=sshcachefs
	$(COVERAGE_BIN) report
	$(COVERAGE_BIN) html

#test: *.py
	#python -v -m unittest $(TCP)
