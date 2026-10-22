# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Real Chrome rendering/downloads against the independent oracle, on an isolated server.
# SPDX-License-Identifier: MIT
import hashlib
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
import traceback

from playwright.sync_api import sync_playwright, expect

from core.architecture.result_registry import new_run, verify_run, write_json
from p05_studio.p00_app.server import Handler, Studio, Job
from p03_experiments.p51_ppa_audit.oracle import ROOT, Sources, compare, flatten, check


class QuietHandler(Handler):
    def log_message(self, *args):
        pass


def main():
    experiment = Path(__file__).parent
    audit = ROOT / json.loads((experiment / 'latest.json').read_text())['audit']
    record = json.loads((audit / 'metadata.json').read_text())
    out = new_run(experiment / 'p02_browser')
    print(out, flush=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
    server.studio = Studio(out / 'p01_results/p01_runs')
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_address[1]}'
    source, checks, errors, failure = Sources(), [], [], None
    def passed(name):
        checks.append(name)
        print('PASS', name, flush=True)
    try:
        with sync_playwright() as tool:
            browser = tool.chromium.launch(channel='chrome', headless=True)
            page = browser.new_page(viewport={'width': 1550, 'height': 1100}, accept_downloads=True)
            page.set_default_timeout(15000)
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(url)
            page.wait_for_function('!state.loading')
            labels = ['frozen_9x9_5000', 'placement_9_lstp_column_hold_v1', 'placement_2_hp_sustained_drive_v1',
                'go_strong_v1_lstp_sustained_drive_v1', 'go_weak_v1_lstp_column_hold_v1']
            for label in labels:
                folder = ROOT / next(r['run'] for r in record['cases'] if r['label'] == label)
                result = verify_run(folder)
                oracle, _ = compare(result, source)
                config = result['identity']['configuration']['requested']
                # Restore a retained completed search through the real payload/export handlers.
                # No execution thread is started for these fixtures.
                server.studio.runs = folder.parent
                job = Job(config, result['case_id'], False, folder.parent)
                job.status, job.run, job.result, job.sequence = 'complete', folder.name, result, 1
                server.studio.jobs = {job.id: job}
                payload = job.payload()
                page.evaluate('job=>{document.getElementById("execution").value="search";applyConfiguration(job.configuration);attachJob(job);}', payload)
                expect(page.locator('#export-components')).to_have_attribute('aria-disabled', 'false')
                page.evaluate('r=>{state.chartTiming={cycles:r.metrics.core_cycles,phases:r.phase_cycles};renderComponents(r.component_estimates,r.costs);}', result)
                if page.locator('#expand-components').inner_text() == 'Collapse all parts':
                    page.locator('#expand-components').click()
                if label == labels[0]:
                    page.locator('.components-panel').screenshot(path=str(out / 'matched_reference.png'))
                page.locator('#expand-components').click()
                visible = page.locator('#component-rows tr[data-component]').evaluate_all('''rows=>rows.map(row=>({id:row.dataset.component,
                    cells:[...row.querySelectorAll('td')].map(cell=>cell.innerText.split('\\n')[0])}))''')
                inventory = flatten(result['costs']['ledger']['components'])
                by_id = {r['id']: r['cells'] for r in visible}
                assert len(visible) == len(by_id) == len(inventory)
                assert set(by_id) == {part['id'] for part, _ in inventory}
                for part, owner in inventory:
                    cells = by_id[part['id']]
                    if owner in ('chip_io', 'weight_programming'):
                        assert all(cells[i] == 'Excluded' for i in (2, 3, 4))
                        continue
                    if part['id'] != owner:
                        assert cells[3] == cells[4] == 'Included'
                        target = part.get('area_um2')  # Independently checked against raw hierarchy by compare().
                    else:
                        target = oracle[owner]['area_um2']
                        if target is None:
                            assert cells[2] == 'Needs report' and cells[3] == 'Needs estimate'
                        else:
                            assert abs(float(cells[3].replace(',', '')) - oracle[owner]['average_power_mw']) <= .000000501
                        check(int(cells[4].replace(',', '')), oracle[owner]['active_cycles'], 'display cycles ' + owner)
                        check(int(cells[1].replace(',', '')), oracle[owner]['count'], 'display count ' + owner)
                    if target is not None:
                        assert abs(float(cells[2].replace(',', '')) - target) <= .000501
                passed(label + ': every expanded row and displayed number')
                for metric, field, divisor in [('area', 'area_um2', 1e6), ('energy', 'energy_uj', 1), ('power', 'average_power_mw', 1)]:
                    total = sum(r[field] or 0 for r in oracle.values()) / divisor
                    check(float(page.locator('#pie-' + metric).get_attribute('data-total')), total, label + ' chart ' + metric)
                    values = page.locator('#pie-' + metric + ' .pie-legend li').evaluate_all('rows=>rows.map(r=>Number(r.dataset.value))')
                    assert values
                    check(sum(values), total, 'chart slices')
                    missing = sum(r[field] is None for key, r in oracle.items() if key not in ('chip_io', 'weight_programming'))
                    check(int(page.locator('#pie-' + metric).get_attribute('data-missing')), missing, 'chart missing')
                check(float(page.locator('#pie-latency').get_attribute('data-total')), result['metrics']['core_cycles'] / 500, 'exclusive phase chart')
                passed(label + ': four chart totals, slices and missing values')
                downloads = out / 'p00_downloads' / label
                downloads.mkdir(parents=True)
                for selector, name in [('#export-json', 'result.json'), ('#export-csv', 'summary.csv'), ('#export-components', 'components.csv')]:
                    with page.expect_download() as info:
                        page.locator(selector).click()
                    item = info.value
                    item.save_as(downloads / name)
                    assert item.failure() is None
                    assert (downloads / name).read_bytes() == (folder / name).read_bytes()
                passed(label + ': JSON and both CSV downloads byte-identical')
                page.locator('tr[data-component="u_sel"] details summary').click()
                assert page.locator('tr[data-component="u_sel"] details').inner_text().strip()
                passed(label + ': source dropdown readable')

            # Exercise a fresh real workload and its normal live-to-completed UI path.
            page.evaluate('resetRunView()')
            server.studio = Studio(out / 'p01_results/p01_runs')
            page.reload()
            page.wait_for_function('!state.loading')
            page.locator('#advanced').evaluate('e=>e.open=true')
            page.select_option('#case', 'placement_2x2_medium_v1')
            page.select_option('#iterations', '50')
            page.select_option('#execution', 'search')
            page.locator('#animation-speed').fill('100')
            page.locator('#animation-speed').dispatch_event('input')
            page.locator('#run').click()
            page.wait_for_function("state.status==='complete'", timeout=60000)
            job = server.studio.jobs[page.evaluate('state.job')]
            result = verify_run(job.runs / job.run)
            oracle, _ = compare(result, source)
            expect(page.locator('#export-components')).to_have_attribute('aria-disabled', 'false')
            for metric, field, divisor in [('area', 'area_um2', 1e6), ('energy', 'energy_uj', 1), ('power', 'average_power_mw', 1)]:
                check(float(page.locator('#pie-' + metric).get_attribute('data-total')), sum(r[field] or 0 for r in oracle.values()) / divisor, 'real run ' + metric)
            check(float(page.locator('#pie-latency').get_attribute('data-total')), result['metrics']['core_cycles'] / 500, 'real run latency')
            passed('real 50-iteration search: live/completed charts match raw-source oracle')
            page.select_option('#iterations', '200')
            for selector in ('#energy', '#power', '#latency'):
                expect(page.locator(selector)).to_have_text('—')
            expect(page.locator('#export-components')).to_have_attribute('aria-disabled', 'true')
            expect(page.locator('#pie-energy')).to_have_attribute('data-ready', 'false')
            passed('configuration change clears old PPA and exports')
            page.set_viewport_size({'width': 430, 'height': 932})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
            passed('mobile page fits viewport')
            assert not errors, errors
            passed('no browser errors')
            browser.close()
    except Exception:
        failure = traceback.format_exc()
        print(failure, flush=True)
    finally:
        server.shutdown()
        server.server_close()
    write_json(out / 'metadata.json', {'status': 'failed' if failure else 'passed', 'checks': checks,
        'failure': failure, 'browser_errors': errors, 'source_audit': str(audit.relative_to(ROOT)),
        'method': 'Five retained verified payloads rendered through real UI; real download endpoints; one new isolated 50-iteration search',
        'user_studio_controlled': False, 'cpu_gpu_benchmarks_executed': False})
    (out / 'SHA256SUMS').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + str(p.relative_to(out)) + '\n'
        for p in sorted(out.rglob('*')) if p.is_file() and p.name != 'SHA256SUMS'))
    if failure:
        raise RuntimeError('Browser audit failed: ' + str(out))


if __name__ == '__main__':
    main()
