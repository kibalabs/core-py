install:
	@ pip install -r requirements.txt -r requirements-dev.txt

list-outdated: install
	@ pip list -o

lint-check:
	@ lint-check *.py ./core

lint-check-ci:
	@ lint-check *.py ./core --output-file lint-check-results.json --output-format annotations

lint-fix:
	@ isort --sl -l 1000 ./core
	@ lint-check *.py ./core

type-check:
	@ type-check *.py ./core

type-check-ci:
	@ type-check *.py ./core --output-file type-check-results.json --output-format annotations

security-check:
	@ security-check *.py ./core

security-check-ci:
	@ security-check *.py ./core --output-file security-check-results.json --output-format annotations

build:
	@ echo "Not Supported"

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

.PHONY: *
