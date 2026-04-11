# Makefile for sca_tool
PYTHON ?= python3
VENV_DIR ?= .venv
PIP := $(VENV_DIR)/bin/pip
PY := $(VENV_DIR)/bin/python

REQ := requirements.txt

.PHONY: help venv install run format lint test clean vault-create vault-open workspace-create

help:
	@echo "Available targets:"
	@echo "  make venv			 -> create virtualenv"
	@echo "  make install		  -> install dependencies"
	@echo "  make run			  -> run main.py"

venv:
	@echo "Creating virtualenv in $(VENV_DIR)"
	$(PYTHON) -m venv $(VENV_DIR)
	@echo "Activate it with: source $(VENV_DIR)/bin/activate"

install: venv
	@echo "Installing dependencies from $(REQ)"
	$(PIP) install --upgrade pip
	$(PIP) install -r $(REQ)

run:
	$(PY) main.py