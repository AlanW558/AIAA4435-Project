"""Small synthetic fixtures for export parsing and ordinal-analysis safeguards."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

import numpy as np
from openpyxl import Workbook

SCRIPT=Path(__file__).resolve().parents[1]/'analyze_wjx_results.py'
SPEC=importlib.util.spec_from_file_location('wjx_analysis',SCRIPT)
analysis=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


class WjxAnalysisTests(unittest.TestCase):
    def test_cannot_judge_is_missing_not_eight_or_midpoint(self):
        for answer in (8,'8',None,'','(空)','（空）'):
            self.assertTrue(np.isnan(analysis.rating(answer)))
        self.assertEqual(analysis.rating('4'),4)
        for answer in (0,9,-1,'garbage'):
            with self.assertRaises(ValueError):analysis.rating(answer)

    def test_holm_known_family_and_original_order(self):
        np.testing.assert_allclose(analysis.holm([.03,.001,.04,.01]),[.06,.004,.06,.03])

    def test_single_item_distribution_keeps_valid_denominator(self):
        d=analysis.describe([1,4,7,np.nan])
        self.assertEqual((d['n'],d['missing'],d['low'],d['neutral'],d['high']),(3,1,1,1,1))
        self.assertEqual(d['mean'],4)

    def test_no_preference_is_a_real_category_code(self):
        self.assertEqual(analysis.code('5',7),5)
        self.assertIsNone(analysis.code('(空)',7))

    def test_zero_votes_has_nonzero_upper_uncertainty(self):
        low,high=analysis.wilson(0,15)
        self.assertAlmostEqual(low,0)
        self.assertAlmostEqual(high,.203883301,places=8)

    def test_friedman_complete_ties_do_not_crash_or_claim_difference(self):
        d=analysis.friedman_permutation(np.ones((3,4)),1)
        self.assertEqual(d['statistic'],0)
        self.assertEqual(d['permutation_p'],1)

    def test_export_schema_and_formula_are_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'synthetic-unit-test.xlsx';book=Workbook();sheet=book.active
            sheet.append(['序号']+[f'{i}. Test question' for i in range(1,33)])
            sheet.append([1]+[1]*32);book.save(p)
            rows,questions,_,_,_=analysis.read_export(p)
            self.assertEqual(len(rows),1);self.assertEqual(len(questions),32)
            sheet['B2']='=1+1';book.save(p)
            with self.assertRaisesRegex(ValueError,'Formula-bearing'):analysis.read_export(p)


if __name__=='__main__':unittest.main()
