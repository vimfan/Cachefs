ID                   :=
SCRIPTS              := scripts
COVERAGE_BIN         := $(shell which coverage)
NOSETESTS_BIN        := $(shell which nosetests-2.7)
GENCSTAGS_BIN        := $(SCRIPTS)/genctags.sh
CLEANUP_BIN          := $(SCRIPTS)/cleanup.sh

WRAPPER              := $(SCRIPTS)/wrapper.sh
DUMMY_WRAPPER        := runner.sh

COVERAGE_ENABLED     := enabled_coverage.sh
COVERAGE_DISABLED    := runner.sh
COVERAGE_REPORT_DIR  := coverage_report

PROFILER_ENABLED     := enabled_profiler.sh
PROFILER_DISABLED    := runner.sh
PROFILER_REPORT_DIR  := profiler_report
PROFILER_CONFIG      := profiler.cfg


.PHONY: enable_coverage enable_profiler disable_wrapper run_test tests coverage profile clean tags

tests: disable_wrapper
	@$(MAKE) -e __run_test

__run_test: 
	$(NOSETESTS_BIN) --with-yanc -v --with-id $(ID)

show_tests:
	$(NOSETESTS_BIN) --collect-only --with-id -v

coverage: enable_coverage
	@$(COVERAGE_BIN) erase
	@rm -Rf $(COVERAGE_REPORT_DIR) && echo "Report dir: $(COVERAGE_REPORT_DIR) cleaned up"
	@$(COVERAGE_BIN) run --branch --source . --omit "*interfaces*" -p  $(NOSETESTS_BIN) --with-yanc -v --with-id $(ID)
	@echo "Combining results..."
	@$(COVERAGE_BIN) combine
	@echo "Generating html report..."
	@$(COVERAGE_BIN) html -d $(COVERAGE_REPORT_DIR)
	@$(COVERAGE_BIN) erase

profile: enable_profiler
	@rm -Rf $(PROFILER_REPORT_DIR)
	@$(MAKE) -e __run_test

enable_profiler:
	@echo $(PROFILER_REPORT_DIR) > $(PROFILER_CONFIG)
	@ln -snf $(PROFILER_ENABLED) $(WRAPPER)
	@echo "Profiler enabled."

enable_coverage:
	@ln -snf $(COVERAGE_ENABLED) $(WRAPPER)
	@echo "Coverage reporing enabled."

disable_wrapper:
	@ln -snf $(DUMMY_WRAPPER) $(WRAPPER)

clean: 
	@$(CLEANUP_BIN)
	@rm -Rf $(PROFILE_REPORT_DIR) && echo "Report dir: $(PROFILE_REPORT_DIR) cleanup up"

tags: 
	$(GENCSTAGS_BIN)
