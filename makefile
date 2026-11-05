install:
	@ pip install uv
	@ uv sync --all-extras

install-updates:
	@ pip install uv
	@ uv sync --upgrade --refresh --all-extras

list-outdated: install
	@ pip list -o

lint-check:
	@ uv run lint-check ./core

lint-check-ci:
	@ uv run lint-check ./core --output-file lint-check-results.json --output-format annotations

lint-fix:
	@ uv run lint-check --fix ./core

type-check:
	@ uv run type-check ./core

type-check-ci:
	@ uv run type-check ./core --output-file type-check-results.json --output-format annotations

build:
	@ uv build

start:
	@ echo "Not Supported"

start-prod:
	@ echo "Not Supported"

test:
	@ uv run test-check tests

test-ci:
	@ uv run test-check tests --output-file test-check-results.json --output-format annotations

clean:
	@ rm -rf ./.mypy_cache ./__pycache__ ./build ./dist

publish: build
	@ uv publish

publish-dev:
	@ uv run publish-dev

.PHONY: *
