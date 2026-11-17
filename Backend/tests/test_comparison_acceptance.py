"""Verify the live acceptance cap using a stubbed provider, never a real key."""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model import DeepSeekModel, ModelError
from unity_comparison_acceptance_server import LimitedComparisonModel


class BudgetTests(unittest.TestCase):
    def test_concurrent_acceptance_calls_share_one_hard_budget_without_fallback(self):
        with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "fixture-not-a-key", "DEEPSEEK_MODEL": "fixture", "DEEPSEEK_BASE_URL": "https://example.invalid", "DEEPSEEK_FALLBACK_API_KEY": "unused-fixture"}):
            model = LimitedComparisonModel()
        self.assertEqual((model.max_attempts, model.fallback_key), (1, ""))
        def request(_):
            try: model._call("fixture", "fixture", {}); return True
            except ModelError: return False
        with patch.object(DeepSeekModel, "_call", return_value=({}, [{"status": "ok"}])) as provider:
            with ThreadPoolExecutor(max_workers=8) as pool: results = list(pool.map(request, range(24)))
        self.assertEqual((sum(results), model.attempts, provider.call_count, len(model.records)), (14, 14, 14, 14))


if __name__ == "__main__": unittest.main()
