#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
"""Replot the supported frozen inputs; never launches simulations or tournaments."""
from pathlib import Path
import argparse,csv,hashlib,json,os,subprocess,sys
ROOT=Path(__file__).resolve().parent
PACKAGE=ROOT.parent
TARGETS=['plot_fig2de.py','plot_fig3a.py','plot_fig3b.py','plot_fig3c.py','plot_fig4.py','plot_extended_bottleneck.py']

def check_inputs():
    records=json.loads((ROOT/'inputs_manifest.json').read_text())
    for row in records:
        p=PACKAGE/row['path']
        actual=hashlib.sha256(p.read_bytes()).hexdigest()
        if actual!=row['sha256']:raise SystemExit(f'Frozen input mismatch: {row["path"]}')
    return len(records)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify-render',action='store_true',help='Compare supported regenerated PDFs with supplied canonical PDFs at 100 dpi, using PyMuPDF.')
    args=parser.parse_args()
    checked=check_inputs()
    out=ROOT/'generated';out.mkdir(exist_ok=True)
    env=dict(os.environ,MPLBACKEND='Agg',PYTHONDONTWRITEBYTECODE='1')
    env.setdefault('MPLCONFIGDIR',str(out/'.mplcache'))
    for target in TARGETS:
        subprocess.run([sys.executable,'-B',str(ROOT/'scripts'/target)],check=True,env=env,cwd=ROOT)
    expected=json.loads((PACKAGE/'data/figure_inputs/comparisons/expected_stacked_ratios.json').read_text())
    actual=json.loads((out/'stacked_ratios.json').read_text())
    if expected!=actual:raise SystemExit('Figure 3c derived numeric ratios differ from archived red-cap result.')
    report={'status':'passed','frozen_inputs_checked':checked,'figure3d':'ON_HOLD_EXCLUDED','targets':TARGETS,'derived_fig3c_ratios_match':True,'scope':'Replot archived CSVs. No new search, training, benchmark, tournament or simulator cost calculation.'}
    if args.verify_render:
        import fitz
        import numpy as np
        results=[]
        for item in json.loads((ROOT/'coverage.json').read_text()):
            if not item.get('generated_asset'):continue
            old=PACKAGE/item['packaged_asset'];new=PACKAGE/item['generated_asset']
            with fitz.open(old) as a,fitz.open(new) as b:
                ap=a[0].get_pixmap(dpi=100,alpha=False);bp=b[0].get_pixmap(dpi=100,alpha=False)
                same=ap.width==bp.width and ap.height==bp.height
                va=np.frombuffer(ap.samples,dtype=np.uint8);vb=np.frombuffer(bp.samples,dtype=np.uint8)
                match=same and np.array_equal(va,vb)
                results.append({'id':item['id'],'pixels_match':bool(match),'reference_pixels':[ap.width,ap.height],'regenerated_pixels':[bp.width,bp.height],'mean_absolute_difference':float(np.abs(va.astype(float)-vb.astype(float)).mean()) if same else None})
        report['render_comparisons']=results
        report['all_rendered_pixels_match']=all(r['pixels_match'] for r in results)
        # Font/render-library differences do not alter numeric reproducibility, and are reported openly.
    (out/'replot_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
