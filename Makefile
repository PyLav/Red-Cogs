.DEFAULT_GOAL := help
PYTHON ?= python3
POETRY ?= poetry
PRECOMMIT ?= pre-commit

ROOT_DIR:=$(shell dirname $(realpath $(firstword $(MAKEFILE_LIST))))


ifneq ($(wildcard $(ROOT_DIR)/venv/.),)
	VENV_PYTHON = $(ROOT_DIR)/venv/bin/python
	VENV_POETRY = $(ROOT_DIR)/venv/bin/poetry
	VENV_PRECOMMIT = $(ROOT_DIR)/venv/bin/pre-commit
else
	VENV_PYTHON = $(PYTHON)
	VENV_POETRY = $(POETRY)
	VENV_PRECOMMIT = $(PRECOMMIT)
endif


define HELP_BODY
Usage:
  make <command>

Commands:
  reformat                   Reformat all staged files being tracked by git.
  full-reformat				 Reformat all files being tracked by git.

  bumpdeps                   Run's Poetry up
  bump						 Bump the packages version
  syncenv                    Sync this project's virtual environment to Red's latest dependencies.
  lock 						 Update the Poetry.lock file
  plugins                    Install all necesarry Poetry Plugins

endef
export HELP_BODY

# Python Code Style
reformat:
	$(VENV_PRECOMMIT) run
full-reformat:
	$(VENV_PRECOMMIT) run --all

# Poetry
bumpdeps:
	$(VENV_POETRY) up --latest
syncenv:
	$(VENV_POETRY) install
lock:
	$(VENV_POETRY) lock
bump:
	$(VENV_POETRY) dynamic-versioning
plugins:
	$(VENV_POETRY) self add "poetry-dynamic-versioning[plugin]"
	$(VENV_POETRY) self add "poetry-plugin-up"
