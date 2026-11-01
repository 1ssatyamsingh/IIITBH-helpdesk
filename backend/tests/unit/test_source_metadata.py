from app.application.ingestion.source_metadata import infer_document_category


def test_fee_structure_category_is_assigned_from_filename():
    metadata = infer_document_category("BTech_Fee_Structure_2019to2025.pdf")

    assert metadata == {
        "document_category": "fee_schedule",
        "document_category_basis": "filename_rule_v1",
    }


def test_academic_calendar_category_is_assigned_from_filename():
    metadata = infer_document_category("2026-27_Academic_Calendar.pdf")

    assert metadata["document_category"] == "academic_calendar"
    assert metadata["document_category_basis"] == "filename_rule_v1"


def test_misspelled_fee_filename_is_still_classified_conservatively():
    metadata = infer_document_category("Fee_Strucure_2025.pdf")

    assert metadata["document_category"] == "fee_schedule"


def test_filename_category_does_not_claim_a_publication_date():
    metadata = infer_document_category("Annual_Report_2022-23.pdf")

    assert "publication_date" not in metadata
    assert "academic_year" not in metadata
