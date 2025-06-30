# ==============================================================================
#
#                         Makefile for Profile Updater
#
# ==============================================================================

# Ensure the script is run with bash
SHELL := /bin/bash

# Load environment variables from .env file if it exists
ifneq (,$(wildcard ./.env))
    include .env
    export
endif

# Default command
.DEFAULT_GOAL := help

# Python interpreter
PYTHON := python3

# Allow passing arguments to python scripts
ARGS := $(wordlist 2,$(words $(MAKECMDGOALS)),$(MAKECMDGOALS))
$(eval $(ARGS):;@:)

# --- Core Commands ---

ascii: ## Generate the ASCII text from your local ascii image
	@echo "🎨  Generating ASCII text from local image..."
	@$(PYTHON) src/generate_ascii.py $(ARGS)

update: check_env ## Update the SVG profiles with latest GitHub stats and ASCII text
	@echo "🚀  Updating SVG profile cards..."
	@$(PYTHON) src/today.py

all: ascii update ## Run the full pipeline: generate ascii and then update profiles
	@echo "✅  Full pipeline finished successfully! Check the 'output' directory."

# --- Helper Commands ---

check_env: ## Check if required environment variables are set
ifndef ACCESS_TOKEN
	$(error "❌ ACCESS_TOKEN is not set. Please create a .env file or export it.")
endif
ifndef USER_NAME
	$(error "❌ USER_NAME is not set. Please create a .env file or export it.")
endif

clean: ## Clean up generated files
	@echo "🧹  Cleaning up generated files..."
	@rm -rf output
	@rm -f ascii.txt ascii.png

install: ## Install dependencies from requirements.txt
	@echo "📦  Installing dependencies..."
	@$(PYTHON) -m pip install -r requirements.txt

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

.PHONY: ascii update all check_env clean install help 