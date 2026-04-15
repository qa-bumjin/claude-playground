PROJECT ?= $(firstword $(wildcard output/active_project/*))
SHEET_NAME ?= $(notdir $(PROJECT))
PYTHON ?= python3

.PHONY: help sync validate export all

help:
	@echo "Usage:"
	@echo "  make all PROJECT=output/active_project/[문서폴더] SHEET_NAME='시트명'"
	@echo "Targets: sync validate export all"
	@echo "Default PROJECT: $(PROJECT)"

sync:
	@test -n "$(PROJECT)" || (echo "ERROR PROJECT is required: output/active_project/[문서폴더]" && exit 1)
	$(PYTHON) scripts/sync_tc_progress.py --project "$(PROJECT)"

validate:
	@test -n "$(PROJECT)" || (echo "ERROR PROJECT is required: output/active_project/[문서폴더]" && exit 1)
	$(PYTHON) scripts/validate_tc_outputs.py --project "$(PROJECT)"

export:
	@test -n "$(PROJECT)" || (echo "ERROR PROJECT is required: output/active_project/[문서폴더]" && exit 1)
	$(PYTHON) scripts/export_tc_excel.py --project "$(PROJECT)" --sheet-name "$(SHEET_NAME)"

all: sync validate export
