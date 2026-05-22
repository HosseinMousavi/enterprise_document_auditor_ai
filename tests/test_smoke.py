from src.models import Issue, AuditReport, SlideSummary
from src.llm_judge import build_llm_payload, semantic_findings_to_issues


def test_issue_dict():
    issue = Issue(
        slide_number=1,
        rule_id="TEST",
        category="Test",
        severity="high",
        title="Test issue",
        evidence="Evidence",
        recommendation="Fix it",
    )
    assert issue.to_dict()["severity"] == "high"


def test_llm_payload_no_api_call():
    issue = Issue(1, "TITLE_DRAFT", "Title slide", "high", "Title slide contains DRAFT", "DRAFT found", "Remove DRAFT")
    report = AuditReport("demo.pptx", 1, [issue], [SlideSummary(1, "Demo", 1, 1, 0, 0)])
    payload = build_llm_payload(report, [issue])
    assert payload["reviewed_issues"][0]["rule_id"] == "TITLE_DRAFT"


def test_semantic_findings_to_issues():
    issues = semantic_findings_to_issues([{"slide_number": 2, "title": "Check headline", "severity": "medium"}])
    assert issues[0].rule_id == "AI_SEMANTIC_REVIEW"
    assert issues[0].severity == "medium"


def test_gemini_config_without_key():
    from src.llm_judge import get_llm_config
    available, provider, model, api_key, endpoint = get_llm_config("Gemini", "gemini-1.5-flash")
    assert provider == "Gemini"
    assert model == "gemini-1.5-flash"
    assert "generativelanguage.googleapis.com" in endpoint
