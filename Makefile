.PHONY: lint test api web

lint:
	uv run ruff check . && uv run ruff format --check .

test:
	uv run pytest -q

api:
	uv run uvicorn orebody.api:app --port 8114 --reload

web:
	cd web && npm run dev -- -p 3014
