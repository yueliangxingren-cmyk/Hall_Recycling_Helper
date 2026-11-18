"""Ensure evaluation cannot label fallback or altered facts a live success."""
import csv
from pathlib import Path
import unittest
from scripts.evaluate import check_answer


class EvaluationTests(unittest.TestCase):
    def setUp(self):
        with (Path(__file__).resolve().parent.parent / 'tests.csv').open(newline='') as stream:
            self.case = next(csv.DictReader(stream))
        self.answer = {key.removeprefix('expected_'): value for key,value in self.case.items() if key.startswith('expected_')}
        self.answer.update(message='Published guidance for "plastic bottle".', grounding='llm')

    def test_fallback_is_quality_pass_but_live_failure(self):
        self.answer['grounding'] = 'published_rule'
        quality, checks = check_answer(self.case, self.answer, live=True)
        self.assertTrue(quality)
        self.assertFalse(checks['live_llm'])
        self.assertTrue(all(check_answer(self.case,self.answer,live=False)[1].values()))

    def test_altered_fact_fails_even_with_live_marker(self):
        self.answer['bin'] = 'Invented bin'
        quality, checks = check_answer(self.case, self.answer, live=True)
        self.assertFalse(quality)
        self.assertFalse(all(checks.values()))

    def test_unapproved_advice_fails(self):
        self.answer['message'] = 'Put everything in the nearest bin.'
        self.assertFalse(check_answer(self.case, self.answer, live=True)[0])
