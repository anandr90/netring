# Makefile for Netring Project

# --- Configuration ---
# Registry host
REGISTRY_HOST = harbor.rajasystems.com
# Registry project/library name
REGISTRY_LIBRARY = library
# Full registry URL for Docker images
REGISTRY_URL = $(REGISTRY_HOST)/$(REGISTRY_LIBRARY)

# Image names
REGISTRY_IMAGE_NAME = netring-registry
MEMBER_IMAGE_NAME = netring-member

# --- Versioning & Platforms ---
# Get current version from git tags, default to v1.0.0 if no tags exist
CURRENT_VERSION := $(shell git describe --tags --abbrev=0 2>/dev/null || echo "v1.0.0")
# Extract version components (major.minor.patch)
MAJOR := $(shell echo $(CURRENT_VERSION) | sed 's/v//' | cut -d. -f1)
MINOR := $(shell echo $(CURRENT_VERSION) | sed 's/v//' | cut -d. -f2)
PATCH := $(shell echo $(CURRENT_VERSION) | sed 's/v//' | cut -d. -f3)
# Find next available patch version (skip existing tags)
NEW_VERSION := $(shell \
	patch=$(PATCH); \
	while [ $$(git tag -l "v$(MAJOR).$(MINOR).$$(expr $$patch + 1)" | wc -l) -gt 0 ]; do \
		patch=$$(expr $$patch + 1); \
	done; \
	echo "v$(MAJOR).$(MINOR).$$(expr $$patch + 1)" \
)
# Allow manual version override
VERSION ?= $(NEW_VERSION)
# Platforms for multi-arch build
PLATFORMS = linux/amd64,linux/arm64
# Buildx builder name
BUILDER_NAME = netring_builder

# Full image names with tags
REGISTRY_IMAGE = $(REGISTRY_URL)/$(REGISTRY_IMAGE_NAME)
MEMBER_IMAGE = $(REGISTRY_URL)/$(MEMBER_IMAGE_NAME)
REGISTRY_IMAGE_TAGGED = $(REGISTRY_IMAGE):$(VERSION)
MEMBER_IMAGE_TAGGED = $(MEMBER_IMAGE):$(VERSION)


# --- Targets ---
.PHONY: all build release buildx-setup clean login help version

help:
	@echo "Usage: make [target]"
	@echo ""
	@echo "Targets:"
	@echo "  release        Auto-increment version and build/push multi-platform release (amd64, arm64)."
	@echo "  build          Build a single-platform image for your local architecture."
	@echo "  buildx-setup   Set up the Docker Buildx builder required for multi-platform builds."
	@echo "  version        Show current and next version information."
	@echo "  login          Display instructions for logging into the Docker registry."
	@echo "  clean          Remove locally built Docker images."
	@echo "  help           Show this help message."

all: build

# Target to login to the container registry.
# This must be run manually before pushing.
login:
	@echo "------------------------------------------------------------------"
	@echo "Please run 'docker login $(REGISTRY_HOST)' to authenticate."
	@echo "------------------------------------------------------------------"

# Target to build single-platform Docker images for the local architecture.
# Useful for local testing.
build:
	@echo "--> Building local platform Docker images with version: $(VERSION)"
	docker build -f docker/Dockerfile.registry -t $(REGISTRY_IMAGE_NAME):$(VERSION) .
	docker build -f docker/Dockerfile.member -t $(MEMBER_IMAGE_NAME):$(VERSION) .
	@echo "--> Local build complete."

# Target to set up the docker buildx builder.
buildx-setup:
	@if ! docker buildx ls | grep -q "$(BUILDER_NAME)"; then \
		echo "--> Creating new buildx builder '$(BUILDER_NAME)'..."; \
		docker buildx create --name $(BUILDER_NAME) --use; \
	else \
		echo "--> Using existing buildx builder '$(BUILDER_NAME)'"; \
		docker buildx use $(BUILDER_NAME); \
	fi
	@echo "--> Builder setup complete."

# Target to show version information
version:
	@echo "Current version: $(CURRENT_VERSION)"
	@echo "Next version:    $(NEW_VERSION)"

# Target to perform a full multi-platform release.
# This auto-increments the version, creates a git tag, and builds/pushes images.
release: buildx-setup
	@echo "--> Current version: $(CURRENT_VERSION)"
	@echo "--> Auto-incrementing to: $(NEW_VERSION)"
	@echo "--> Installing test dependencies..."
	python3 -m pip install --break-system-packages -r requirements.txt
	@echo "--> Running tests before release..."
	python3 run_tests.py unit
	@echo "--> Tests passed! Proceeding with release..."
	@echo "--> Creating git tag $(NEW_VERSION)..."
	git tag $(NEW_VERSION)
	git push origin $(NEW_VERSION)
	@echo "--> Performing multi-platform release for platforms: $(PLATFORMS)"
	@echo "--> Building and pushing registry image..."
	docker buildx build --platform $(PLATFORMS) -f docker/Dockerfile.registry -t $(REGISTRY_IMAGE_TAGGED) -t $(REGISTRY_IMAGE):latest --push .
	@echo "--> Building and pushing member image..."
	docker buildx build --platform $(PLATFORMS) -f docker/Dockerfile.member -t $(MEMBER_IMAGE_TAGGED) -t $(MEMBER_IMAGE):latest --push .
	@echo "------------------------------------------------------------------"
	@echo "✅ Multi-platform release $(VERSION) successfully pushed to $(REGISTRY_URL)"
	@echo "   Platforms: $(PLATFORMS)"
	@echo "   Images:"
	@echo "   - $(REGISTRY_IMAGE_TAGGED)"
	@echo "   - $(REGISTRY_IMAGE):latest"
	@echo "   - $(MEMBER_IMAGE_TAGGED)"
	@echo "   - $(MEMBER_IMAGE):latest"
	@echo "------------------------------------------------------------------"

# Target to clean up local Docker images created by the 'build' target.
# Note: This does not remove images from the registry or multi-platform images from the buildx cache.
clean:
	@echo "--> Cleaning up local Docker images for version $(VERSION)..."
	-docker rmi $(REGISTRY_IMAGE_NAME):$(VERSION)
	-docker rmi $(MEMBER_IMAGE_NAME):$(VERSION)
	@echo "--> Cleanup complete."

