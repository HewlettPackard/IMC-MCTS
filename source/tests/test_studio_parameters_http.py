# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
# Per-browser controls and custom configuration HTTP contract.
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from core.architecture.result_registry import ROOT
from core.architecture import studio_current as c
from p05_studio.p00_app.server import Handler,Studio

class StudioParameterHTTPTests(unittest.TestCase):
    def test_preview_owner_and_origin_contract(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'p03_experiments/p104_simulator_campaign') as folder:
            server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.studio=Studio(Path(folder)/'p01_runs')
            worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
            port=server.server_address[1]
            def request(path,client='a'*32,body=None,origin=None):
                headers={'X-Studio-Client':client}
                if body is not None:headers['Content-Type']='application/json'
                if origin:headers['Origin']=origin
                req=Request('http://127.0.0.1:'+str(port)+path,data=None if body is None else json.dumps(body).encode(),headers=headers)
                try:
                    with urlopen(req,timeout=10) as response:return response.status,json.load(response)
                except HTTPError as error:return error.code,json.load(error)
            try:
                parameters={'adc_lanes':{'energy_pj':90,'service_cycles':26}}
                status,data=request('/api/component-preview',body={'board_size':9,'model_id':'go_strong_v1','component_parameters':parameters})
                self.assertEqual(status,200);self.assertEqual(data['component_parameters'],parameters)
                self.assertEqual(data['architecture']['adc_service_cycles'],26)
                self.assertEqual(request('/api/component-preview',body={'component_parameters':{'adc_lanes':{'energy_pj':-1}}})[0],400)
                self.assertEqual(request('/api/component-preview',body={},origin='http://elsewhere.example')[0],403)
                config=c.current_architecture()['default_configuration'] | {'iterations':3,'component_parameters':parameters}
                status,job=request('/api/jobs',body={'mode':'paused','configuration':config})
                self.assertEqual(status,202);identifier=job['id']
                self.assertEqual(request('/api/jobs/'+identifier,client='b'*32)[0],404)
                self.assertIsNone(request('/api/session',client='b'*32)[1]['job'])
                self.assertEqual(request('/api/session')[1]['job']['id'],identifier)
                self.assertEqual(request('/api/jobs/'+identifier+'/actions',client='b'*32,body={'action':'cancel'})[0],404)
                self.assertEqual(request('/api/jobs',client='b'*32,body={'mode':'paused','configuration':config})[0],400)
                self.assertEqual(request('/api/jobs/'+identifier+'/actions',body={'action':'cancel'})[0],200)
            finally:
                for job in server.studio.jobs.values():job.action('cancel')
                server.shutdown();server.server_close();worker.join(timeout=2)

if __name__=='__main__':unittest.main()
