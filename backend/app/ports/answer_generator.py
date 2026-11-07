from typing import Protocol

from app.domain.retrieval.models import EvidenceSource, GeneratedAnswer


class AnswerGenerator(Protocol):
    def generate(
        self,
        question: str,
        evidence: list[EvidenceSource],
        on_token=None,
    ) -> GeneratedAnswer: ...
