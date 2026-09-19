.PHONY: test lint fix

test:
	python3 -m pytest tests/

lint:
	python3 -m ruff check format_json.py tests/

fix:
	python3 -m ruff check --fix format_json.py tests/
