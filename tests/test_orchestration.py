"""CP2 verification for the unified crawler-to-remediation pipeline."""

from orchestration import _scoring_payload, run_audit


def test_run_audit_uses_complete_backend_pipeline():
    page = "data:text/html,<html><head><title>CP2</title></head><body><p>Accessible content</p></body></html>"

    result = run_audit(page, persona="gptbot", timeout_seconds=10.0, wait_after_load_ms=100)

    assert result["url"] == page
    assert result["persona"] == "gptbot"
    assert result["crawl"]["page"]["title"] == "CP2"
    assert result["scoring"]["score"] == result["summary"]["score"]
    assert result["remediation"]["evidence"]
    assert result["http"] == result["crawl"]["http"]
    assert result["detection"] == result["crawl"]["detection"]


def test_standalone_403_remains_inconclusive_for_scoring():
    crawl_result = {
        "persona": "gptbot",
        "http": {"status_code": 403},
        "detection": {
            "is_blocked": False,
            "inference": {"verdict": "INCONCLUSIVE", "mechanism": "HTTP_FORBIDDEN"},
        },
        "robots_txt": {"status_code": 200, "is_allowed": True},
    }

    payload = _scoring_payload(crawl_result, None)

    assert payload["bots"]["gptbot"]["blocked"] is False
