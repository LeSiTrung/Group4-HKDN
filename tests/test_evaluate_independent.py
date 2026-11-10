"""Checks for the independent recorder; no answer/prompt tuning."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('evaluate_independent', Path(__file__).resolve().parents[1] / 'scripts/evaluate_independent.py')
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class IndependentRecorderTests(unittest.TestCase):
    def test_frozen_hash_and_scripted_history_are_preserved(self):
        dataset, digest = runner.load_dataset()
        self.assertEqual(digest, runner.EXPECTED_HASH)
        self.assertEqual(len(dataset['cases']), 20)
        case = next(case for case in dataset['cases'] if case.get('prior_turns'))
        request = runner.payload(case)
        self.assertEqual(request['history'], case['prior_turns'])
        self.assertNotIn('book_ids', request['history'][-1])
        self.assertNotIn('conversation_id', request)

    def test_oracle_rejects_nonlocal_requests_and_preserves_none(self):
        def generator(question, rows):
            import httpx
            httpx.Client().get('https://example.com/')
        case = {'id': 'test', 'question': 'test', 'source_refs': ['knowledge:1']}
        result = runner.oracle(case, {'knowledge:1': {'id': 1, 'answer': 'test'}}, 'hash', generator)
        self.assertIn('only loopback Ollama', result['error'])
        self.assertFalse(result['model_http_observed'])
        result = runner.oracle(case, {'knowledge:1': {'id': 1, 'answer': 'test'}}, 'hash', lambda q, r: None)
        self.assertIsNone(result['validated_generation'])
        self.assertFalse(result['model_http_observed'])


if __name__ == '__main__':
    unittest.main()
