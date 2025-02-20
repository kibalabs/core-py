install:
	@ pip install uv
	@ uv sync

install-updates:
	@ pip install uv
	@ uv sync

list-outdated: install
	@ pip list -o

lint-check:
	@ lint-check ./core

lint-check-ci:
	@ lint-check ./core --output-file lint-check-results.json --output-format annotations

lint-fix:
	@ isort --sl -l 1000 ./core
	@ lint-check ./core

type-check:
	@ type-check ./core

type-check-ci:
	@ type-check ./core --output-file type-check-results.json --output-format annotations

security-check:
	@ security-check ./core

security-check-ci:
	@ security-check ./core --output-file security-check-results.json --output-format annotations

build:
	@ uv build

start:
	@ echo "Not Supported"

start-prod:
	@ echo "Not Supported"

test:
	@ python -m pytest tests -v

test-ci:
# NOTE(krishan711): implement this in build-py
	@ python -m pytest tests -v

clean:
	@ rm -rf ./.mypy_cache ./__pycache__ ./build ./dist

publish: build
	@ uv publish

GIT_LAST_TAG=$(shell git describe --tags --abbrev=0)
GIT_COUNT=$(shell git rev-list $(GIT_LAST_TAG)..HEAD --count)
publish-dev:
	@ version --part dev --count $(GIT_COUNT)
	@ uv build
	@ uv publish

.PHONY: *
