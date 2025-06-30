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

# --- Core Commands ---

art: ## Generate the ASCII art from your local ascii image
	@echo "🎨  Generating ASCII art from local image..."
	@$(PYTHON) src/generate_ascii.py

update: check_env ## Update the SVG profiles with latest GitHub stats and ASCII art
	@echo "🚀  Updating SVG profile cards..."
	@$(PYTHON) src/today.py

all: art update ## Run the full pipeline: generate art and then update profiles
	@echo "✅  Full pipeline finished successfully!"

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
	@rm -f ascii_art.txt
	@rm -rf cache

install: ## Install dependencies from requirements.txt
	@echo "📦  Installing dependencies..."
	@$(PYTHON) -m pip install -r requirements.txt

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

.PHONY: art update all check_env clean install help 