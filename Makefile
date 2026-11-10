.PHONY: install test cov lint typecheck survey judge report all clean

install:
	uv sync --extra dev

test:
	uv run pytest -p no:cacheprovider

cov:
	uv run pytest --cov-report=html -p no:cacheprovider

lint:
	uv run ruff check src tests scripts

typecheck:
	uv run mypy src

survey:
	uv run python scripts/run_survey.py

judge:
	uv run python scripts/run_judge.py

report:
	uv run python scripts/analyze.py

all: lint typecheck test survey judge report

clean:
	rm -rf .pytest_cache .coverage htmlcov
	find results -type f ! -name '.gitkeep' -delete
