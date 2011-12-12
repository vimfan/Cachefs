ID :=
SCRIPTS              := scripts
COVERAGE_BIN         := $(shell which coverage)
NOSETESTS_BIN        := $(shell which nosetests-2.7)
GENCSTAGS_BIN        := $(SCRIPTS)/genctags.sh
CLEANUP_BIN          := $(SCRIPTS)/cleanup.sh

COVERAGE             := $(SCRIPTS)/coverage.sh
COVERAGE_ENABLED     := enabled_coverage.sh
COVERAGE_DISABLED 	 := disabled_coverage.sh
COVERAGE_REPORT_DIR  := tests/coverage_report


.PHONY: disable_coverage enable_coverage clean tags

disable_coverage:
	@ln -snf $(COVERAGE_DISABLED) $(COVERAGE)

enable_coverage:
	@ln -snf $(COVERAGE_ENABLED) $(COVERAGE)
	@echo "Coverage reporing enabled."

test: disable_coverage
	$(NOSETESTS_BIN) --with-yanc -v --with-id $(ID)

coverage: enable_coverage
	@$(COVERAGE_BIN) erase
	@rm -Rf $(COVERAGE_REPORT_DIR) && echo "Report dir: $(COVERAGE_REPORT_DIR) cleaned up"
	@$(COVERAGE_BIN) run --branch --source . --omit "*interfaces*" -p  $(NOSETESTS_BIN) --with-yanc -v --with-id $(ID)
	@echo "Combining results..."
	@$(COVERAGE_BIN) combine
	@echo "Generating html report..."
	@$(COVERAGE_BIN) html -d $(COVERAGE_REPORT_DIR)
	@$(COVERAGE_BIN) erase

clean: 
	@$(CLEANUP_BIN)

tags: 
	$(GENCSTAGS_BIN)
