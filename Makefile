ID=
COVERAGE_BIN=/usr/bin/coverage

dummy:
	echo ""

tags: dummy
	scripts/genctags.sh

tests:
	nosetests-2.7 -v 
test:
	nosetests-2.7 -v --with-id $(ID)

coverage:
	nosetests-2.7 -v --with-coverage --cover-package=sshcachefs
	$(COVERAGE_BIN) report
	$(COVERAGE_BIN) html

clean: 
	find . -name "*.pyc" -o -name "*.swp" | xargs rm -f
	scripts/cleanup.sh
