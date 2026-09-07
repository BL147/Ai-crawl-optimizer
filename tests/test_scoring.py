"""
tests/test_scoring.py - Scoring Engine Tests
Covers: determinism, no-double-counting, no fabricated baseline,
multi-persona aggregation, total_deductions invariant.
"""
import sys, os, unittest, copy
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scoring import calculate_score

# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------

def _accessible():
    return {
        "bots": {"gptbot": {
            "status": 200, "waf": None, "captcha": False, "latency_ms": 140,
            "blocked": False, "verdict": "ACCESSIBLE", "mechanism": "NONE",
            "confidence": 1.0, "signals": [],
        }},
        "browser": {"status": None, "latency_ms": 0, "is_real": False},
        "robots_txt": {"ai_disallowed": False},
        "waf_detected": None, "captcha_detected": False,
        "selective_ai_block_detected": False,
    }

def _blocked_403_no_waf():
    """HTTP 403, blocked verdict, NO WAF evidence."""
    return {
        "bots": {"gptbot": {
            "status": 403, "waf": None, "captcha": False, "latency_ms": 95,
            "blocked": True, "verdict": "BLOCKED", "mechanism": "HTTP_FORBIDDEN",
            "confidence": 0.9, "signals": [],
        }},
        "browser": {"status": None, "latency_ms": 0, "is_real": False},
        "robots_txt": {"ai_disallowed": False},
        "waf_detected": None, "captcha_detected": False,
        "selective_ai_block_detected": False,
    }

def _blocked_403_with_cloudflare():
    """HTTP 403, blocked verdict, Cloudflare WAF confirmed."""
    return {
        "bots": {"gptbot": {
            "status": 403, "waf": "Cloudflare", "captcha": False, "latency_ms": 95,
            "blocked": True, "verdict": "BLOCKED", "mechanism": "CLOUDFLARE_BLOCK",
            "confidence": 0.95, "signals": [],
        }},
        "browser": {"status": None, "latency_ms": 0, "is_real": False},
        "robots_txt": {"ai_disallowed": False},
        "waf_detected": "Cloudflare", "captcha_detected": False,
        "selective_ai_block_detected": False,
    }

def _blocked_with_real_browser_baseline():
    """AI blocked (403 + Cloudflare) while REAL browser baseline = 200."""
    return {
        "bots": {"gptbot": {
            "status": 403, "waf": "Cloudflare", "captcha": False, "latency_ms": 95,
            "blocked": True, "verdict": "BLOCKED", "mechanism": "CLOUDFLARE_BLOCK",
            "confidence": 0.95, "signals": [],
        }},
        "browser": {"status": 200, "latency_ms": 180, "is_real": True, "blocked": False},
        "robots_txt": {"ai_disallowed": False},
        "waf_detected": "Cloudflare", "captcha_detected": False,
        "selective_ai_block_detected": False,
    }

def _blocked_no_real_baseline():
    """AI blocked but NO real browser baseline (is_real=False)."""
    return {
        "bots": {"gptbot": {
            "status": 403, "waf": "Cloudflare", "captcha": False, "latency_ms": 95,
            "blocked": True, "verdict": "BLOCKED", "mechanism": "CLOUDFLARE_BLOCK",
            "confidence": 0.95, "signals": [],
        }},
        "browser": {"status": None, "latency_ms": 0, "is_real": False},
        "robots_txt": {"ai_disallowed": False},
        "waf_detected": "Cloudflare", "captcha_detected": False,
        "selective_ai_block_detected": False,
    }

def _inconclusive_403():
    return {
        "bots": {"gptbot": {
            "status": 403, "waf": None, "captcha": False, "latency_ms": 120,
            "blocked": False, "verdict": "INCONCLUSIVE", "mechanism": "NONE",
            "confidence": 0.0, "signals": [],
        }},
        "browser": {"status": None, "latency_ms": 0, "is_real": False},
        "robots_txt": {"ai_disallowed": False},
        "waf_detected": None, "captcha_detected": False,
        "selective_ai_block_detected": False,
    }

def _robots_disallowed():
    return {
        "bots": {"gptbot": {
            "status": 200, "waf": None, "captcha": False, "latency_ms": 140,
            "blocked": False, "verdict": "ACCESSIBLE", "mechanism": "NONE",
            "confidence": 1.0, "signals": [],
        }},
        "browser": {"status": None, "latency_ms": 0, "is_real": False},
        "robots_txt": {"ai_disallowed": True, "details": "Disallow: /"},
        "waf_detected": None, "captcha_detected": False,
        "selective_ai_block_detected": False,
    }

def _multi_persona_mixed():
    """Two personas: one accessible, one WAF-blocked."""
    return {
        "bots": {
            "gptbot": {
                "status": 403, "waf": "Cloudflare", "captcha": False, "latency_ms": 95,
                "blocked": True, "verdict": "BLOCKED", "mechanism": "CLOUDFLARE_BLOCK",
                "confidence": 0.95, "signals": [],
            },
            "claudebot": {
                "status": 200, "waf": None, "captcha": False, "latency_ms": 150,
                "blocked": False, "verdict": "ACCESSIBLE", "mechanism": "NONE",
                "confidence": 1.0, "signals": [],
            },
        },
        "browser": {"status": None, "latency_ms": 0, "is_real": False},
        "robots_txt": {"ai_disallowed": False},
        "waf_detected": None, "captcha_detected": False,
        "selective_ai_block_detected": False,
    }


# =========================================================================
# TEST CLASSES
# =========================================================================

class TestScoringDeterminism(unittest.TestCase):
    def _check(self, data, label):
        r1 = calculate_score(data)
        r2 = calculate_score(copy.deepcopy(data))
        self.assertEqual(r1["score"], r2["score"], f"[{label}] score non-deterministic")
        self.assertEqual(r1["total_deductions"], r2["total_deductions"],
                         f"[{label}] total_deductions non-deterministic")
        self.assertEqual(len(r1["penalties"]), len(r2["penalties"]),
                         f"[{label}] penalty count non-deterministic")

    def test_det_accessible(self): self._check(_accessible(), "accessible")
    def test_det_blocked_no_waf(self): self._check(_blocked_403_no_waf(), "blocked_no_waf")
    def test_det_blocked_cloudflare(self): self._check(_blocked_403_with_cloudflare(), "cloudflare")
    def test_det_inconclusive(self): self._check(_inconclusive_403(), "inconclusive")
    def test_det_robots(self): self._check(_robots_disallowed(), "robots")
    def test_det_multi(self): self._check(_multi_persona_mixed(), "multi_persona")


class TestScoreInvariant(unittest.TestCase):
    """total_deductions must always == sum(p['points_deducted'] for p in penalties)"""
    def _check(self, data, label):
        r = calculate_score(data)
        raw_sum = sum(p["points_deducted"] for p in r["penalties"])
        self.assertEqual(r["total_deductions"], raw_sum,
                         f"[{label}] total_deductions ({r['total_deductions']}) != "
                         f"sum(points_deducted) ({raw_sum})")
        # And score = max(0, 100 - raw_sum)
        expected_score = max(0, 100 - raw_sum)
        self.assertEqual(r["score"], expected_score,
                         f"[{label}] score={r['score']} but expected {expected_score}")

    def test_inv_accessible(self): self._check(_accessible(), "accessible")
    def test_inv_blocked_no_waf(self): self._check(_blocked_403_no_waf(), "blocked_no_waf")
    def test_inv_blocked_cloudflare(self): self._check(_blocked_403_with_cloudflare(), "cloudflare")
    def test_inv_inconclusive(self): self._check(_inconclusive_403(), "inconclusive")
    def test_inv_robots(self): self._check(_robots_disallowed(), "robots")
    def test_inv_multi(self): self._check(_multi_persona_mixed(), "multi_persona")


class TestAccessibleSite(unittest.TestCase):
    def test_accessible_scores_100(self):
        r = calculate_score(_accessible())
        self.assertEqual(r["score"], 100)
        self.assertEqual(r["total_deductions"], 0)
        self.assertEqual(len(r["penalties"]), 0)
        self.assertEqual(r["grade"], "A")


class TestNoDoubleCountingHTTP403WAF(unittest.TestCase):
    """
    HTTP 403 + Cloudflare WAF from the same bot = ONE compound penalty.
    Must NOT produce both 'HTTP 403' and 'WAF challenge' as separate entries.
    """
    def test_waf_block_is_one_compound_penalty(self):
        r = calculate_score(_blocked_403_with_cloudflare())
        # Should have exactly ONE access-denial penalty
        access_denial = [p for p in r["penalties"] if p.get("category") == "Access Denial"]
        self.assertEqual(len(access_denial), 1,
                         f"Expected 1 compound Access Denial penalty, got {len(access_denial)}: "
                         f"{[p['factor'] for p in access_denial]}")
        # The single penalty must mention WAF
        factor = access_denial[0]["factor"]
        self.assertIn("WAF", factor, f"Expected WAF in compound factor, got: {factor}")

    def test_no_duplicate_waf_and_http_penalties(self):
        r = calculate_score(_blocked_403_with_cloudflare())
        categories = [p["category"] for p in r["penalties"]]
        # There must NOT be two separate "Anti-Bot & WAF" and "HTTP Status" for same event
        old_waf_count = sum(1 for p in r["penalties"]
                            if "Anti-Bot" in p.get("category", "") or
                               "HTTP Status" in p.get("category", ""))
        self.assertEqual(old_waf_count, 0,
                         f"Old-style double-penalty categories still present: {categories}")

    def test_blocked_no_waf_is_single_plain_block(self):
        r = calculate_score(_blocked_403_no_waf())
        access_denial = [p for p in r["penalties"] if p.get("category") == "Access Denial"]
        self.assertEqual(len(access_denial), 1)
        # Should NOT mention WAF
        self.assertNotIn("WAF", access_denial[0]["factor"])


class TestDiscriminationOnlyWithRealBaseline(unittest.TestCase):
    def test_discrimination_fires_with_real_baseline(self):
        r = calculate_score(_blocked_with_real_browser_baseline())
        discrim = [p for p in r["penalties"]
                   if p.get("category") == "Selective AI Discrimination"]
        self.assertEqual(len(discrim), 1,
                         "Expected exactly 1 discrimination penalty with real baseline")

    def test_no_discrimination_without_real_baseline(self):
        r = calculate_score(_blocked_no_real_baseline())
        discrim = [p for p in r["penalties"]
                   if p.get("category") == "Selective AI Discrimination"]
        self.assertEqual(len(discrim), 0,
                         f"Discrimination penalty must NOT fire without real baseline: {discrim}")


class TestInconclusiveVsConfirmedBlock(unittest.TestCase):
    def test_inconclusive_scores_higher_than_confirmed_block(self):
        r_inc = calculate_score(_inconclusive_403())
        r_blk = calculate_score(_blocked_403_no_waf())
        self.assertGreater(r_inc["score"], r_blk["score"],
                           "Inconclusive 403 must score higher than confirmed block")
        self.assertLess(r_inc["total_deductions"], r_blk["total_deductions"],
                        "Inconclusive must deduct fewer points than confirmed block")


class TestRobotsDeduction(unittest.TestCase):
    def test_robots_disallowed_causes_deduction(self):
        r = calculate_score(_robots_disallowed())
        self.assertLess(r["score"], 100)
        factors = [p["factor"] for p in r["penalties"]]
        self.assertTrue(any("Robots" in f for f in factors),
                        f"Expected robots.txt penalty, got: {factors}")


class TestMultiPersonaAggregation(unittest.TestCase):
    def test_multi_persona_score_based_on_all_bots(self):
        """Score must reflect the blocked bot, not just the accessible one."""
        r_multi = calculate_score(_multi_persona_mixed())
        r_single_accessible = calculate_score(_accessible())
        # Mixed (one blocked, one accessible) must score LOWER than all-accessible
        self.assertLess(r_multi["score"], r_single_accessible["score"],
                        "Multi-persona with one blocked bot must score lower than all-accessible")
        self.assertGreater(r_multi["total_deductions"], 0,
                           "Multi-persona with blocked bot must have deductions > 0")

    def test_multi_persona_penalty_mentions_blocked_bot(self):
        r = calculate_score(_multi_persona_mixed())
        all_evidence = []
        for p in r["penalties"]:
            all_evidence.extend(p.get("evidence", []))
        all_evidence_str = " ".join(all_evidence)
        # gptbot was blocked, must appear in evidence
        self.assertIn("gptbot", all_evidence_str,
                      f"Blocked bot 'gptbot' must appear in evidence. Got: {all_evidence_str}")


class TestResultSchema(unittest.TestCase):
    required = {"score", "grade", "risk_level", "reasons", "metrics",
                "penalties", "total_deductions", "base_score"}

    def _check(self, data, label):
        r = calculate_score(data)
        missing = self.required - set(r.keys())
        self.assertEqual(missing, set(), f"[{label}] Missing keys: {missing}")
        for p in r["penalties"]:
            self.assertIn("reason", p, f"Missing 'reason' in penalty: {p}")
            self.assertIn("points_deducted", p, f"Missing 'points_deducted' in penalty: {p}")
            self.assertIn("evidence", p, f"Missing 'evidence' in penalty: {p}")
            self.assertGreater(p["points_deducted"], 0)

    def test_schema_accessible(self): self._check(_accessible(), "accessible")
    def test_schema_blocked(self): self._check(_blocked_403_with_cloudflare(), "blocked")
    def test_schema_inconclusive(self): self._check(_inconclusive_403(), "inconclusive")


if __name__ == "__main__":
    unittest.main()
