# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
import unittest

from core.architecture.verification import exit_code, summarize


class VerificationReportTests(unittest.TestCase):
    def test_missing_evidence_cannot_pass(self):
        report = summarize([])
        self.assertTrue(all(row['status'] == 'UNVERIFIED' for row in report['stages'].values()))
        self.assertEqual(exit_code(report), 0)
        self.assertEqual(exit_code(report, strict=True), 2)
        self.assertFalse(report['publication_ready'])

    def test_failure_dominates_missing_evidence(self):
        report = summarize([{'stage':'algorithm','status':'FAIL','name':'divergence'}])
        self.assertEqual(report['stages']['algorithm']['status'], 'FAIL')
        self.assertEqual(exit_code(report), 1)
        self.assertEqual(exit_code(report, strict=True), 1)

    def test_passing_subset_does_not_certify_whole_flow(self):
        report = summarize([{'stage':'circuit','status':'PASS','name':'integer arithmetic'},
            {'stage':'circuit','status':'UNVERIFIED','name':'analog accuracy'}])
        self.assertEqual(report['stages']['circuit']['status'], 'UNVERIFIED')
        self.assertFalse(report['all_stages_verified'])


if __name__ == '__main__':
    unittest.main()
