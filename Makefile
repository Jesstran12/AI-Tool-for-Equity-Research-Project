.PHONY: lint test api web demo-data

lint:
	uv run ruff check . && uv run ruff format --check .

test:
	uv run pytest -q

demo-data:
	uv run python tests/fixtures/make_demo_data.py data

api:
	uv run uvicorn orebody.api:app --port 8114 --reload

web:
	cd web && npm run dev -- -p 3014
