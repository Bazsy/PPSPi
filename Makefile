SHELL := /bin/bash
PYTHON ?= python3

PYTHON_FILES := files/ppstime scripts tests
SHELL_FILES := scripts/install.sh scripts/build-image.sh scripts/package-release.sh \
	scripts/validate-image.sh \
	pi-gen/stage-pps-pi/prerun.sh pi-gen/stage-pps-pi/01-install/00-run.sh

.PHONY: help test lint lint-python lint-shell format-check yaml-check actionlint markdownlint build-image clean

help:
	@printf '%s\n' \
		'make test          Run standard-library unit and fixture tests' \
		'make lint          Run all installed static checks' \
		'make build-image   Build the Trixie arm64 image through Docker' \
		'make clean         Remove local build output'

test:
	$(PYTHON) -m unittest discover -s tests -v

lint: lint-python lint-shell format-check yaml-check actionlint markdownlint

lint-python:
	ruff check $(PYTHON_FILES)

lint-shell:
	shellcheck $(SHELL_FILES)

format-check:
	shfmt -d -i 4 -ci -sr $(SHELL_FILES)

yaml-check:
	yamllint .

actionlint:
	actionlint

markdownlint:
	markdownlint-cli2

build-image:
	./scripts/build-image.sh

clean:
	rm -rf artifacts build dist .pi-gen