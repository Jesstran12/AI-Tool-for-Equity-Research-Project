from pathlib import Path

import pytest

from tests.fixtures.make_pdf import make_report


@pytest.fixture(scope="session")
def fixture_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return make_report(tmp_path_factory.mktemp("pdf") / "fixture_report.pdf")
