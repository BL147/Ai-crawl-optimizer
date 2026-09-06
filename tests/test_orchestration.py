"""CP2 verification for the unified crawler-to-remediation pipeline."""

from orchestration import run_audit


def test_run_audit_uses_complete_backend_pipeline():
    page = "data:text/html,<html><head><title>CP2</title></head><body><p>Accessible content</p></body></html>"

    result = run_audit(page, persona="gptbot", timeout_seconds=10.0, wait_after_load_ms=100)

    assert result["url"] == page
    assert result["persona"] == "gptbot"
    assert result["crawl"]["page"]["title"] == "CP2"
    assert result["scoring"]["score"] == result["summary"]["score"]
    assert result["remediation"]["observed_facts"]
    assert result["http"] == result["crawl"]["http"]
    assert result["detection"] == result["crawl"]["detection"]
