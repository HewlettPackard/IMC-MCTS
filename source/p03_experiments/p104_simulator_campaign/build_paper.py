# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
from pathlib import Path
import shutil,subprocess,sys,json
ROOT=Path.cwd();RUN=ROOT/'p03_experiments/p104_simulator_campaign/p00_runs/run_20261003_063318Z'
name=sys.argv[1];source=RUN/'p02_paper_refresh/working'/name;out=RUN/'p03_pdf'/name
out.mkdir(parents=True,exist_ok=True)
for path in source.iterdir():
    if path.is_file() and path.suffix in ['.bib','.bst','.bbl']:shutil.copy2(path,out/path.name)
latex=['/Library/TeX/texbin/pdflatex','-interaction=nonstopmode','-halt-on-error',f'-output-directory={out}','main.tex']
for step,cmd in enumerate([latex,['/Library/TeX/texbin/bibtex','main'],latex,latex]):
    result=subprocess.run(cmd,cwd=out if step==1 else source,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (out/f'compile-{step+1}.txt').write_text(result.stdout+result.stderr)
    if result.returncode:print('\n'.join((result.stdout+result.stderr).splitlines()[-40:]));raise SystemExit(result.returncode)
print(name,'compiled',out/'main.pdf',flush=True)
