install:
	@ pip install -r requirements.txt -r requirements-dev.txt

list-outdated: install
	@ pip list -o

lint-check:
	@ lint --directory ./core

lint-check-ci:
	@ lint --directory ./core --output-file lint-check-results.json --output-format annotations

lint-fix:
	@ isort --sl -l 1000 ./core
	@ lint --directory ./core

type-check:
	@ type-check --directory ./core

type-check-ci:
	@ type-check --directory ./core --output-file type-check-results.json --output-format annotations

security-check:
	@ security-check --directory ./core

security-check-ci:
	@ security-check --directory ./core --output-file security-check-results.json --output-format annotations

build:
	@ echo "Not Supported"

start:
	@ echo "Not Supported"

start-prod:
	@ echo "Not Supported"

test:
	@ echo "Not Supported"

clean:
	@ rm -rf ./.mypy_cache ./__pycache__ ./build ./dist

.PHONY: *
