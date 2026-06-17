from pathlib import Path

import pytest


@pytest.fixture
def cloud_root(tmp_path: Path) -> Path:
    root = tmp_path / "cloud"
    root.mkdir()
    return root
