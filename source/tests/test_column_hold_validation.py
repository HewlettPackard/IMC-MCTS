# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Do not let buffered result identities silently outlive their hardware proof.
# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import tempfile
import unittest

from core.architecture.column_hold_validation import VALIDATION, validate_buffered_sources


class ColumnHoldValidationTests(unittest.TestCase):
    def test_current_binding_and_exclusions(self):
        proof=validate_buffered_sources()
        self.assertEqual(proof['nominal_9x9_h96']['inference_cycles'],26701)
        self.assertIn('host Go rules, metadata and interfaces',proof['excluded'])
        self.assertIn('core/architecture/analog_readout.py',proof['validated_sources'])

    def test_stale_sources_and_unaccepted_evidence_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'proof.json'
            for change in ('source','status','evidence'):
                proof=json.loads(VALIDATION.read_text())
                if change=='source': proof['validated_sources']['core/architecture/analog_readout.py']='0'*64
                elif change=='status': proof['status']='smoke_only'
                else: proof['evidence']['metadata_sha256']='0'*64
                path.write_text(json.dumps(proof))
                with self.subTest(change=change), self.assertRaises(ValueError): validate_buffered_sources(path)


if __name__=='__main__': unittest.main()
