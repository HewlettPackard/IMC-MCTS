# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
# Cost revisions must bind new evidence without relabeling saved ledgers.
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from core.architecture import studio_current as current
from core.architecture.connected_costs import SOURCE_FILES
from p05_studio.p00_app.server import Handler


class ConnectedStudioIdentityTests(unittest.TestCase):
    def response(self,path,runs):
        # Exercise the real GET routing without opening a socket or starting a job.
        handler=object.__new__(Handler)
        handler.path=path;handler.server=SimpleNamespace(studio=SimpleNamespace(runs=runs))
        replies=[];handler.send_data=lambda status,data,*args:replies.append((status,data))
        handler.do_GET()
        self.assertEqual(replies[0][0],200)
        return replies[0][1]

    def test_health_preview_and_bound_sources_agree(self):
        data=current.preview('go_strong_v1')
        health=self.response('/api/health',Path('.'))
        self.assertEqual(health['profile'],data['architecture']['profile'])
        self.assertEqual(health['cost_model_profile'],data['cost_model_profile'])
        self.assertEqual(health['cost_model_sha256'],data['cost_model_sha256'])
        self.assertEqual(health['connected_synthesis'],data['connected_synthesis'])
        for path in SOURCE_FILES:
            name=str(path.relative_to(current.ROOT))
            self.assertEqual(data['source_sha256'][name],hashlib.sha256(path.read_bytes()).hexdigest())
        parts={row['id']:row for row in data['components']}
        group=parts['u_ucb']
        self.assertEqual(len(group['children']),16)
        self.assertTrue(all(child['counted'] is False for child in group['children']))
        self.assertAlmostEqual(group['details']['native65_part']['area_um2'],
            sum(child['details']['native65_part']['area_um2'] for child in group['children']))

    def test_saved_v5_identity_is_response_only(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);runs=root/'p01_runs';runs.mkdir()
            out=runs/'run_20261010_000000Z';out.mkdir()
            result={'costs':{'ledger':{'profile':'ucb16_adc32_buffered_estimate_v5','sha256':'original-v5-digest'}}}
            (out/'result.json').write_text(json.dumps(result))
            index={'schema_version':1,'cases':{'old':{'run':out.name,'execution_profile':current.PROFILE}}}
            (root/'index.json').write_text(json.dumps(index))
            before={path:path.read_bytes() for path in (root/'index.json',out/'result.json')}
            saved=self.response('/api/runs',runs)['cases']['old']
            self.assertEqual(saved['execution_profile'],current.PROFILE)
            self.assertEqual(saved['cost_model_profile'],'ucb16_adc32_buffered_estimate_v5')
            self.assertEqual(saved['cost_model_sha256'],'original-v5-digest')
            self.assertNotEqual(saved['cost_model_profile'],current.COST_PROFILE)
            self.assertTrue(all(path.read_bytes()==value for path,value in before.items()))
            play=root/'p02_plays'/out.name;play.mkdir(parents=True)
            (play/'result.json').write_bytes(before[out/'result.json'])
            (play/'metadata.json').write_text(json.dumps({'status':'complete','completed_moves':2,'architecture_profile':current.PROFILE}))
            (play/'SHA256SUMS').write_text('')
            original=(play/'result.json').read_bytes()
            session=self.response('/api/plays',runs)['sessions'][0]
            self.assertEqual(session['architecture_profile'],current.PROFILE)
            self.assertEqual(session['cost_model_profile'],'ucb16_adc32_buffered_estimate_v5')
            self.assertEqual((play/'result.json').read_bytes(),original)

    def test_custom_search_and_session_architecture_match_cost_digest(self):
        from core.architecture.result_registry import ROOT,configuration,run_case,verify_run
        from p05_studio.p00_app.placement_play import BoardPlay
        config=configuration(current.current_architecture()['default_configuration'] |
            {'board_size':2,'model_id':'random_diagnostic','iterations':3,
             'component_parameters':{'u_ucb':{'idle_dynamic_mw':20}}})
        with tempfile.TemporaryDirectory(dir=ROOT/'p03_experiments/p91_studio_latest_architecture') as folder:
            out,result=run_case(custom=config,runs=Path(folder)/'p01_runs')
            verify_run(out)
            digest=result['costs']['ledger']['sha256']
            self.assertEqual(result['architecture']['cost_model_sha256'],digest)
            self.assertEqual(result['identity']['configuration']['current_architecture']['cost_model_sha256'],digest)
            play=BoardPlay(config,Path(folder)/'p02_plays')
            out,game=play.run(lambda *args:None,lambda *args:None,lambda p:'finish' if len(p.moves)==2 else None)
            verify_run(out)
            digest=game['costs']['ledger']['sha256']
            self.assertEqual(game['identity']['architecture']['cost_model_sha256'],digest)
            self.assertEqual(game['architecture']['cost_model_sha256'],digest)
            self.assertEqual(game['component_estimates']['architecture']['cost_model_sha256'],digest)


if __name__=='__main__':unittest.main()
