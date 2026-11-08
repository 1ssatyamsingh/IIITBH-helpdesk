from pathlib import Path

from app.core.config import Settings


def test_default_data_directory_is_inside_backend_package_root():
    expected = Path(__file__).resolve().parents[2] / "data"
    assert Settings().data_dir == expected


def test_wildcard_cors_origin_is_rejected_with_credentials():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(frontend_origins="*")


def test_cors_origins_are_normalized_and_unique():
    settings = Settings(frontend_origins=" https://app.example.edu,https://app.example.edu ")
    assert settings.cors_origins == ["https://app.example.edu"]


def test_resolved_embedding_model_id_tracks_selected_provider():
    local = Settings(embedding_provider="local")
    cloudflare = Settings(embedding_provider="cloudflare")

    assert local.resolved_embedding_model_id == local.embedding_model_id
    assert cloudflare.resolved_embedding_model_id == cloudflare.cloudflare_embedding_model_id
