.PHONY: lint test api web demo-data fetch-mari

MARI_FS_URL = https://marimaca.com/wp-content/uploads/2026/07/25-10-09-Marimaca-Oxide-Deposit-NI-43-101-Technical-Report-Feasibility-Study_FINAL.pdf
MARI_FS_PDF = data/raw/MARI/2025-08-25_MarimacaOxide_FS_NI43-101.pdf
MARI_FS_SHA = 304cebd3a54345684938132d7f00f3f456647184ac03475c88b3decb8c89222b

lint:
	uv run ruff check . && uv run ruff format --check .

test:
	uv run pytest -q

demo-data:
	uv run python tests/fixtures/make_demo_data.py data

fetch-mari:  # downloads the public MARI feasibility study (18 MB) and checks its sha256
	mkdir -p data/raw/MARI
	curl -sSL -o $(MARI_FS_PDF) "$(MARI_FS_URL)"
	echo "$(MARI_FS_SHA)  $(MARI_FS_PDF)" | shasum -a 256 -c -

api:
	uv run uvicorn orebody.api:app --port 8114 --reload

web:
	cd web && npm run dev -- -p 3014
