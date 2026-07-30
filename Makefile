SHELL := /bin/bash

PORT ?= 8000
COLIMA_PROFILE ?= default
ENV_FILE ?= .env
DOCKER_WORKFLOW := ./scripts/docker-workflow.sh

.DEFAULT_GOAL := help

.PHONY: help docker-test docker-logs docker-publish docker-clean docker-verify

help:
	@echo "Homebox Companion container workflow"
	@echo
	@echo "  make docker-test       Build and run the AMD64 image with Colima"
	@echo "  make docker-logs       Follow logs from the local test container"
	@echo "  make docker-publish    Push the tested image as sha-<commit> and latest"
	@echo "  make docker-clean      Remove local test artifacts and owned Colima runtime"
	@echo "  make docker-verify     Verify public GHCR access and AMD64 availability"
	@echo
	@echo "Overrides: PORT=8000 COLIMA_PROFILE=default ENV_FILE=.env"

docker-test:
	@PORT="$(PORT)" COLIMA_PROFILE="$(COLIMA_PROFILE)" ENV_FILE="$(ENV_FILE)" $(DOCKER_WORKFLOW) test

docker-logs:
	@COLIMA_PROFILE="$(COLIMA_PROFILE)" $(DOCKER_WORKFLOW) logs

docker-publish:
	@COLIMA_PROFILE="$(COLIMA_PROFILE)" $(DOCKER_WORKFLOW) publish

docker-clean:
	@COLIMA_PROFILE="$(COLIMA_PROFILE)" $(DOCKER_WORKFLOW) clean

docker-verify:
	@$(DOCKER_WORKFLOW) verify
