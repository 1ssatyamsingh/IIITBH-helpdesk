from pathlib import Path

CATEGORY_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("academic_calendar", ("academic calendar", "calendar")),
    ("fee_schedule", ("fee structure", "fee_structure", "fee strucure", "fees")),
    ("annual_report", ("annual report", "annual_report")),
    ("annual_accounts", ("annual accounts", "annual_accounts")),
    ("ordinance", ("ordinance", "ordinances")),
    ("admission_instructions", ("admission test", "reporting", "admission")),
    ("information_brochure", ("brochure", "information brochure")),
    ("hostel_form", ("hostel registration", "hostel leave", "undertaking")),
    ("medical_services", ("medical", "empanelment")),
    ("institute_statute", ("statute", "ppp act")),
)


def infer_document_category(filename: str) -> dict[str, str]:
    """Assign a conservative category from filename tokens; never infer publication dates."""
    normalized = Path(filename).stem.lower().replace("%20", " ").replace("_", " ").replace("-", " ")
    for category, tokens in CATEGORY_RULES:
        if any(token in normalized for token in tokens):
            return {
                "document_category": category,
                "document_category_basis": "filename_rule_v1",
            }
    return {
        "document_category": "general_institute_information",
        "document_category_basis": "filename_rule_v1",
    }
