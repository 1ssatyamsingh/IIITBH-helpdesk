import json
from pathlib import Path

import pymupdf
import pytest

from app.infrastructure.extraction.groq_qwen_vlm_extractor import (
    GroqQwenVlmExtractor,
    VlmConfigurationError,
)


class FakeResponse:
    def __init__(self, body: dict) -> None:
        self.body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.body


class FakeHttpClient:
    def __init__(self, body: dict) -> None:
        self.body = body
        self.request = None

    def post(self, url: str, **kwargs):
        self.request = {"url": url, **kwargs}
        return FakeResponse(self.body)


def _make_scanned_pdf(path: Path) -> None:
    pixmap = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 100, 100), 0)
    pixmap.clear_with(200)
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_image(pymupdf.Rect(30, 30, 300, 300), pixmap=pixmap)
    doc.save(path)
    doc.close()


def test_groq_qwen_vlm_sends_page_image_and_returns_transcription(tmp_path: Path) -> None:
    pdf_path = tmp_path / "scan.pdf"
    _make_scanned_pdf(pdf_path)
    body = {
        "choices": [
            {
                "message": {
                    "content": json.dumps({"text": "IIIT Bhagalpur — Fee Notice", "warnings": []})
                }
            }
        ]
    }
    fake_http = FakeHttpClient(body)
    extractor = GroqQwenVlmExtractor(
        api_key="test-secret",
        http_client=fake_http,
    )

    page = extractor.extract_page(pdf_path, 1)

    assert page.text == "IIIT Bhagalpur — Fee Notice"
    assert page.page_number == 1
    assert page.extraction_method.value == "groq_qwen_vlm"
    assert fake_http.request["json"]["model"] == "qwen/qwen3.8-27b"
    image_url = fake_http.request["json"]["messages"][1]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/jpeg;base64,")
    assert fake_http.request["json"]["response_format"] == {"type": "json_object"}


def test_groq_vlm_requires_api_key() -> None:
    with pytest.raises(VlmConfigurationError, match="GROQ_API_KEY"):
        GroqQwenVlmExtractor(api_key=None)
