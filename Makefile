# Dockerfile Builder
# ==================
#
# All the content is in `docker-bits`; this Makefile
# just builds target dockerfiles by combining the dockerbits.
#
# Management of build, pull/push, and testing is modified from
# https://github.com/jupyter/docker-stacks
#
# Tests/some elements of makefile strongly inspired by
# https://github.com/jupyter/docker-stacks/blob/master/Makefile

# The docker-stacks tag
DOCKER-STACKS-UPSTREAM-TAG := ed2908bbb62e

tensorflow-CUDA := 11.8.0
pytorch-CUDA    := 11.8.0

# Misc Directories
TESTS_DIR := ./tests
MAKE_HELPERS := ./make_helpers
PYTHON_VENV := .venv

# Executables
PYTHON := $(PYTHON_VENV)/bin/python
POST_BUILD_HOOK := post-build-hook.sh
BAKE_BUILD_EXEC := bake-build.sh

# Default labels
DEFAULT_REPO := k8scc01covidacr.azurecr.io
GIT_SHA := $(shell git rev-parse HEAD)
# This works during local development, but if on a GitHub PR it will resolve to "HEAD"
# so don't rely on it when on the GH runners!
DEFAULT_TAG := $(shell ./make_helpers/get_branch_name.sh)
BRANCH_NAME := $(shell ./make_helpers/get_branch_name.sh)

# Other
DEFAULT_PORT := 8888
DEFAULT_NB_PREFIX := /notebook/username/notebookname

# Available images to test
AVAILABLE_IMAGES := $(notdir $(wildcard images/*/))
FINAL_IMAGES := base mid sas-kernel jupyterlab-cpu sas

# Autocomplete support
.PHONY: help _list-images bake test test-smoke test-fast test-coverage dev push post-build
.PHONY: install-python-dev-venv check-python-venv check-port-available check-test-prereqs

###################################
######    Default Help Menu   ######
###################################

help: ## Show all available commands
	@echo "================================================================================"; \
	echo "Zone Kubeflow Containers - Available Commands"; \
	echo "================================================================================"; \
	echo ""; \
	echo "BUILDING:"; \
	echo "  make bake/<image>                 Build a specific image"; \
	echo "  make push/<image>                 Push image to registry"; \
	echo ""; \
	echo "TESTING:"; \
	echo "  make test                         Quick smoke tests for all images"; \
	echo "  make test/<image>                 Full test suite for specific image"; \
	echo "  make test-fast/<image>            Skip slow/integration tests"; \
	echo "  make test-smoke/<image>           Critical tests only (fast)"; \
	echo ""; \
	echo "DEVELOPMENT:"; \
	echo "  make dev/<image>                  Launch container interactively"; \
	echo "  make install-python-dev-venv      Setup development Python environment"; \
	echo ""; \
	echo "AVAILABLE IMAGES:"; \
	for img in $(FINAL_IMAGES); do echo "  • $$img"; done; \
	echo ""; \
	echo "EXAMPLES:"; \
	echo "  make bake/jupyterlab-cpu && make test/jupyterlab-cpu"; \
	echo "  make test-smoke/base"; \
	echo "  make dev/mid"; \
	echo ""

###################################
######    Docker helpers     ######
###################################

bake/%: export DARGS?=
bake/%: export BASE_IMAGE?=
bake/%: export REPO?=$(DEFAULT_REPO)
bake/%: export TAGS?=
bake/%: ## build the desired image with docker bake
	IMAGE_NAME="$(notdir $@)" \
	bash "$(MAKE_HELPERS)/$(BAKE_BUILD_EXEC)"

post-build/%: export REPO?=$(DEFAULT_REPO)
post-build/%: export TAG?=$(DEFAULT_TAG)
post-build/%: export SOURCE_FULL_IMAGE_NAME?=
post-build/%: export IMAGE_VERSION?=
post-build/%: export IS_LATEST?=
post-build/%:
	# TODO: could check for custom hook in the build's directory
	IMAGE_NAME="$(notdir $@)" \
	GIT_SHA=$(GIT_SHA) \
	BRANCH_NAME=$(BRANCH_NAME) \
	bash "$(MAKE_HELPERS)/$(POST_BUILD_HOOK)"

push/%: DARGS?=
push/%: REPO?=$(DEFAULT_REPO)
push/%:
	REPO=$$(echo "$(REPO)" | sed 's:/*$$:/:' | sed 's:^\s*/*\s*$$::') &&\
	echo "Pushing the following tags for $${REPO}$(notdir $@) (all tags)" &&\
	docker images $${REPO}$(notdir $@) --format="{{ .Tag }}" &&\
	docker push --all-tags $(DARGS) "$${REPO}"$(notdir $@)

###################################
######     Image Testing     ######
###################################

check-python-venv:
	@if $(PYTHON) --version> /dev/null 2>&1; then \
		echo "Found dev python venv via $(PYTHON)"; \
	else \
		echo -n 'No dev python venv found at $(PYTHON)\n' \
				'Please run `make install-python-dev-venv` to build a dev python venv'; \
		exit 1; \
	fi

check-port-available:
	@if curl http://localhost:$(DEFAULT_PORT) > /dev/null 2>&1; then \
		echo "Port $(DEFAULT_PORT) busy - clear port or change default before continuing"; \
		exit 1; \
	fi

check-test-prereqs: check-python-venv check-port-available

test: ## Test all images automatically and show summary report
	make _test-all

_test-all: ## Internal target: test all images with smoke tests (fast validation)
	@echo ""; \
	echo "=============================================================================="; \
	echo "Testing all available images (smoke tests - critical tests only)..."; \
	echo "Total images to test: $$(echo $(FINAL_IMAGES) | wc -w)"; \
	echo "=============================================================================="; \
	success=true; \
	passed=0; \
	failed=0; \
	for img in $(FINAL_IMAGES); do \
		echo ""; \
		echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
		echo "Processing: $$img"; \
		echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"; \
		echo ""; \
		echo "[1/2] Building image: $$img..."; \
		if ! make bake/$$img > /dev/null 2>&1; then \
			echo "❌ Failed to build $$img"; \
			failed=$$((failed + 1)); \
			success=false; \
			continue; \
		fi; \
		echo "✓ Image built successfully"; \
		echo ""; \
		echo "[2/2] Running smoke tests for: $$img..."; \
		echo "(Running critical tests only - full suite available via 'make test-fast/<image>')"; \
		if make test-smoke/$$img; then \
			echo ""; \
			echo "✓ Smoke tests PASSED for $$img"; \
			passed=$$((passed + 1)); \
		else \
			echo ""; \
			echo "❌ Smoke tests FAILED for $$img"; \
			failed=$$((failed + 1)); \
			success=false; \
		fi; \
	done; \
	echo ""; \
	echo "=============================================================================="; \
	echo "TEST SUMMARY (Smoke Tests)"; \
	echo "=============================================================================="; \
	echo "✓ Passed: $$passed"; \
	echo "❌ Failed: $$failed"; \
	echo "=============================================================================="; \
	echo ""; \
	echo "For more thorough testing use:"; \
	echo "  make test-fast/<image>       - Skip slow/integration tests"; \
	echo "  make test/<image>            - Run full test suite"; \
	echo ""; \
	if [ "$$success" = true ]; then \
		echo "✓ All images passed smoke tests!"; \
		exit 0; \
	else \
		echo "❌ Some images failed smoke tests. Review details above."; \
		exit 1; \
	fi

install-python-dev-venv:
	python3 -m venv $(PYTHON_VENV)
	$(PYTHON) -m pip install -Ur requirements-dev.txt
	$(PYTHON) -m pip list

test-smoke/%: REPO?=$(DEFAULT_REPO)
test-smoke/%: TAG?=$(DEFAULT_TAG)
test-smoke/%: NB_PREFIX?=$(DEFAULT_NB_PREFIX)
test-smoke/%: check-test-prereqs ## Run smoke tests for a specific image
	REPO=$$(echo "$(REPO)" | sed 's:/*$$:/:' | sed 's:^\s*/*\s*$$::') ;\
	TESTS="$(TESTS_DIR)/general";\
	SPECIFIC_TEST_DIR="$(TESTS_DIR)/$(notdir $@)";\
	if [ ! -d "$${SPECIFIC_TEST_DIR}" ]; then\
		echo "No specific tests found for $${SPECIFIC_TEST_DIR}.  Running only general tests";\
	else\
		TESTS="$${TESTS} $${SPECIFIC_TEST_DIR}";\
		echo "Found specific tests folder";\
	fi;\
	echo "Running smoke tests on folders '$${TESTS}'";\
	IMAGE_NAME="$${REPO}$(notdir $@):$(TAG)" NB_PREFIX=$(DEFAULT_NB_PREFIX) $(PYTHON) -m pytest -m "smoke" $${TESTS} -v

test-fast/%: REPO?=$(DEFAULT_REPO)
test-fast/%: TAG?=$(DEFAULT_TAG)
test-fast/%: NB_PREFIX?=$(DEFAULT_NB_PREFIX)
test-fast/%: check-test-prereqs ## Run fast tests (skip slow/integration) for a specific image
	REPO=$$(echo "$(REPO)" | sed 's:/*$$:/:' | sed 's:^\s*/*\s*$$::') ;\
	TESTS="$(TESTS_DIR)/general";\
	SPECIFIC_TEST_DIR="$(TESTS_DIR)/$(notdir $@)";\
	if [ ! -d "$${SPECIFIC_TEST_DIR}" ]; then\
		echo "No specific tests found for $${SPECIFIC_TEST_DIR}.  Running only general tests";\
	else\
		TESTS="$${TESTS} $${SPECIFIC_TEST_DIR}";\
		echo "Found specific tests folder";\
	fi;\
	echo "Running fast tests on folders '$${TESTS}'";\
	IMAGE_NAME="$${REPO}$(notdir $@):$(TAG)" NB_PREFIX=$(DEFAULT_NB_PREFIX) $(PYTHON) -m pytest -m "not slow and not integration" $${TESTS} -v

test-coverage/%: REPO?=$(DEFAULT_REPO)
test-coverage/%: TAG?=$(DEFAULT_TAG)
test-coverage/%: NB_PREFIX?=$(DEFAULT_NB_PREFIX)
test-coverage/%: check-test-prereqs ## Run tests with coverage for a specific image
	REPO=$$(echo "$(REPO)" | sed 's:/*$$:/:' | sed 's:^\s*/*\s*$$::') ;\
	TESTS="$(TESTS_DIR)/general";\
	SPECIFIC_TEST_DIR="$(TESTS_DIR)/$(notdir $@)";\
	if [ ! -d "$${SPECIFIC_TEST_DIR}" ]; then\
		echo "No specific tests found for $${SPECIFIC_TEST_DIR}.  Running only general tests";\
	else\
		TESTS="$${TESTS} $${SPECIFIC_TEST_DIR}";\
		echo "Found specific tests folder";\
	fi;\
	echo "Running tests with coverage on folders '$${TESTS}'";\
	IMAGE_NAME="$${REPO}$(notdir $@):$(TAG)" NB_PREFIX=$(DEFAULT_NB_PREFIX) $(PYTHON) -m pytest --cov=tests --cov-report=html --cov-report=xml:coverage.xml --cov-report=term $${TESTS} -v; \
	echo "Coverage report generated in htmlcov/index.html and coverage.xml"

test/%: REPO?=$(DEFAULT_REPO)
test/%: TAG?=$(DEFAULT_TAG)
test/%: NB_PREFIX?=$(DEFAULT_NB_PREFIX)
test/%: check-test-prereqs ## Run all tests for a specific image
	# End repo with exactly one trailing slash, unless it is empty
	REPO=$$(echo "$(REPO)" | sed 's:/*$$:/:' | sed 's:^\s*/*\s*$$::') ;\
	TESTS="$(TESTS_DIR)/general";\
	SPECIFIC_TEST_DIR="$(TESTS_DIR)/$(notdir $@)";\
	if [ ! -d "$${SPECIFIC_TEST_DIR}" ]; then\
		echo "No specific tests found for $${SPECIFIC_TEST_DIR}.  Running only general tests";\
	else\
		TESTS="$${TESTS} $${SPECIFIC_TEST_DIR}";\
		echo "Found specific tests folder";\
	fi;\
	echo "Running tests on folders '$${TESTS}'";\
	IMAGE_NAME="$${REPO}$(notdir $@):$(TAG)" NB_PREFIX=$(DEFAULT_NB_PREFIX) $(PYTHON) -m pytest -m "not info" $${TESTS}

dev/%: ARGS?=
dev/%: DARGS?=
dev/%: NB_PREFIX?=$(DEFAULT_NB_PREFIX)
dev/%: PORT?=8888
dev/%: REPO?=$(DEFAULT_REPO)
dev/%: TAG?=$(DEFAULT_TAG)
dev/%: ## run a foreground container for a stack (useful for local testing)
	# End repo with exactly one trailing slash, unless it is empty
	REPO=$$(echo "$(REPO)" | sed 's:/*$$:/:' | sed 's:^\s*/*\s*$$::') ;\
	IMAGE_NAME="$${REPO}$(notdir $@):$(TAG)" ;\
	echo "\n###############\nLaunching docker container.  Connect to it via http://localhost:$(PORT)$(NB_PREFIX)\n###############\n" ;\
	if xdg-open --version > /dev/null; then\
		( sleep 5 && xdg-open "http://localhost:8888$(NB_PREFIX)" ) & \
	else\
		( sleep 5 && open "http://localhost:8888$(NB_PREFIX)" ) &  \
	fi; \
	docker run -it --rm -p $(PORT):8888 -e NB_PREFIX=$(NB_PREFIX) $(DARGS) $${IMAGE_NAME} $(ARGS)
