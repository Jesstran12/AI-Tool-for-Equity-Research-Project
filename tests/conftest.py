from pathlib import Path

import pytest

from tests.fixtures.make_pdf import make_report


@pytest.fixture(scope="session")
def fixture_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_report(tmp_path_factory.mktemp("pdf") / "fixture_report.pdf")


@pytest.fixture(scope="session")
def fixture_extracted(fixture_pdf: Path, tmp_path_factory: pytest.TempPathFactory):
    from orebody.ingest.extract import extract_pages

    return extract_pages(fixture_pdf, tmp_path_factory.mktemp("pages"))


@pytest.fixture(scope="session")
def fixture_index(fixture_extracted):
    from orebody.index.ni43101 import build_index, load_patterns
    from orebody.ingest.extract import read_page

    pages = [
        read_page(fixture_extracted.pages_dir, n) for n in range(1, fixture_extracted.n_pages + 1)
    ]
    return build_index(
        pages, load_patterns(Path(__file__).resolve().parents[1] / "config" / "sections.yaml")
    )
