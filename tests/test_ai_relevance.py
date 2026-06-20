import json
import unittest
from pathlib import Path

from scripts.ai_relevance import add_ai_relevance_fields, is_ai_related_record, score_ai_relevance


class AiRelevanceScoringTests(unittest.TestCase):
    def test_scores_strong_ai_signal_with_reason(self):
        rec = {
            "site_id": "techurls",
            "site_name": "TechURLs",
            "source": "Hacker News",
            "title": "OpenAI releases new GPT model",
            "url": "https://example.com/ai",
        }
        result = score_ai_relevance(rec)
        self.assertTrue(result["is_ai_related"])
        self.assertGreaterEqual(result["score"], 0.65)
        self.assertEqual(result["label"], "model_release")
        self.assertIn("openai", result["signals"])
        self.assertIn("matched_ai_signal", result["reason"])

    def test_rejects_broad_model_without_tech_context(self):
        rec = {
            "site_id": "buzzing",
            "site_name": "Buzzing",
            "source": "general",
            "title": "这个商业模型终于跑通了",
            "url": "https://example.com/model",
        }
        result = score_ai_relevance(rec)
        self.assertFalse(result["is_ai_related"])
        self.assertLess(result["score"], 0.65)
        self.assertEqual(result["reason"], "missing_meaningful_ai_signal")

    def test_accepts_broad_ai_plus_tech_context(self):
        rec = {
            "site_id": "techurls",
            "site_name": "TechURLs",
            "source": "GitHub",
            "title": "开源推理框架支持更多GPU后端",
            "url": "https://example.com/inference-gpu",
        }
        result = score_ai_relevance(rec)
        self.assertTrue(result["is_ai_related"])
        self.assertGreaterEqual(result["score"], 0.65)
        self.assertEqual(result["reason"], "matched_broad_ai_plus_tech_signal")
        self.assertIn("gpu", result["signals"])

    def test_accepts_agent_context_as_developer_tool(self):
        rec = {
            "site_id": "opmlrss",
            "site_name": "OPML RSS",
            "source": "BestBlogs.dev",
            "title": "分层记忆：Agent 中的上下文管理",
            "url": "https://example.com/agent-context",
        }
        result = score_ai_relevance(rec)
        self.assertTrue(result["is_ai_related"])
        self.assertGreaterEqual(result["score"], 0.65)
        self.assertEqual(result["label"], "agent_workflow")

    def test_trusted_ai_source_defaults_to_keep(self):
        rec = {
            "site_id": "aihot",
            "site_name": "AI HOT",
            "source": "AI HOT",
            "title": "今日值得关注的产品更新",
            "url": "https://aihot.virxact.com/post/1",
        }
        result = score_ai_relevance(rec)
        self.assertTrue(result["is_ai_related"])
        self.assertGreaterEqual(result["score"], 0.65)
        self.assertEqual(result["reason"], "trusted_ai_source_default_keep")

    def test_adds_public_debug_fields(self):
        rec = {
            "site_id": "official_ai",
            "site_name": "Official AI Updates",
            "source": "GitHub Changelog",
            "title": "GitHub Copilot adds a coding agent",
            "url": "https://example.com/copilot-agent",
        }
        out = add_ai_relevance_fields(rec)
        self.assertTrue(out["ai_is_related"])
        self.assertIn("ai_score", out)
        self.assertIn("ai_label", out)
        self.assertIn("ai_relevance_reason", out)
        self.assertIn("ai_signals", out)
        self.assertTrue(is_ai_related_record(rec))

    def test_url_path_and_query_do_not_create_ai_relevance(self):
        rec = {
            "site_id": "buzzing",
            "site_name": "Buzzing",
            "source": "finance.yahoo.com",
            "title": "这家公司的商业模型终于跑通了",
            "url": "https://example.com/news/openai-gpt-agent-model?topic=ai",
        }

        result = score_ai_relevance(rec)

        self.assertFalse(result["is_ai_related"])
        self.assertLess(result["score"], 0.65)
        self.assertNotIn("openai", result["signals"])
        self.assertNotIn("gpt", result["signals"])

    def test_url_host_can_still_contribute_source_identity(self):
        rec = {
            "site_id": "opmlrss",
            "site_name": "OPML RSS",
            "source": "Product Updates",
            "title": "New product notes for developers",
            "url": "https://openai.com/news/product-notes",
        }

        result = score_ai_relevance(rec)

        self.assertTrue(result["is_ai_related"])
        self.assertGreaterEqual(result["score"], 0.65)
        self.assertIn("openai", result["signals"])

    def test_url_host_scoring_strips_credentials_and_port(self):
        rec = {
            "site_id": "opmlrss",
            "site_name": "OPML RSS",
            "source": "Product Updates",
            "title": "New product notes for developers",
            "url": "https://token@example.com:8443/news/openai-gpt-agent",
        }

        result = score_ai_relevance(rec)

        self.assertFalse(result["is_ai_related"])
        self.assertNotIn("openai", result["signals"])
        self.assertNotIn("gpt", result["signals"])

    def test_rejects_non_ai_agent_model_business_context(self):
        rec = {
            "site_id": "buzzing",
            "site_name": "Buzzing",
            "source": "MarketWatch",
            "title": "Insurance agent adopts a new commission model",
            "url": "https://example.com/insurance-agent-commission-model",
        }

        result = score_ai_relevance(rec)

        self.assertFalse(result["is_ai_related"])
        self.assertLess(result["score"], 0.65)

    def test_adds_split_score_fields_while_preserving_ai_score(self):
        rec = {
            "site_id": "official_ai",
            "site_name": "Official AI Updates",
            "source": "Anthropic News",
            "title": "Claude adds a desktop agent workflow",
            "url": "https://www.anthropic.com/news/desktop-agent",
        }

        out = add_ai_relevance_fields(rec)

        self.assertEqual(out["score_version"], "ai_relevance_scoring_v0_5")
        self.assertEqual(out["ai_score"], out["ai_relevance_score"])
        self.assertGreaterEqual(out["source_trust_score"], 0)
        self.assertGreaterEqual(out["priority_score"], out["ai_relevance_score"])

    def test_golden_fixture_records_expected_relevance_decisions(self):
        fixture_path = Path(__file__).parent / "fixtures" / "ai_relevance_golden.json"
        cases = json.loads(fixture_path.read_text(encoding="utf-8"))

        self.assertGreaterEqual(len(cases), 8)
        for case in cases:
            with self.subTest(case=case["name"]):
                result = score_ai_relevance(case["record"])
                self.assertEqual(result["is_ai_related"], case["is_ai_related"])
                if case["is_ai_related"]:
                    self.assertGreaterEqual(result["score"], 0.65)
                    for signal in case.get("required_signals", []):
                        self.assertIn(signal, result["signals"])
                else:
                    self.assertLess(result["score"], 0.65)


if __name__ == "__main__":
    unittest.main()
