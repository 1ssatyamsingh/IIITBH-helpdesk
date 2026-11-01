from pathlib import Path

from app.core.config import Settings


def test_default_data_directory_is_inside_backend_package_root():
    expected = Path(__file__).resolve().parents[2] / "data"
    assert Settings().data_dir == expected
