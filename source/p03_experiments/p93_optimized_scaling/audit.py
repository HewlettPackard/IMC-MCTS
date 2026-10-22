# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# Reconcile supplied cell values and separate the architectural assumptions.
# SPDX-License-Identifier: MIT
import hashlib,json
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from core.architecture.crossbar_workbook import workbook_source,SOURCES
from core.architecture.parallel_datapath import SizedParallelDatapathGoSimulation
from core.architecture.board_sizing import board_hardware,memory_characterization,memory_profile_name
from core.architecture.sram_costs import load_sram_profile

HERE=Path(__file__).resolve().parent
source=workbook_source()
with ZipFile(SOURCES/'crossbar_reference.xlsx') as archive:
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    book=ET.fromstring(archive.read('xl/workbook.xml'))
    sheets=book.find('s:sheets',ns)
    sheet=next(i+1 for i,e in enumerate(sheets) if e.attrib['name']=='New_Architecture')
    cells={c.attrib['r']:c for c in ET.fromstring(archive.read(f'xl/worksheets/sheet{sheet}.xml')).findall('.//s:c',ns)}
    supplied=[]
    for cell,name,unit in [('C14','cell_area','um2'),('L14','on_resistance','Mohm'),('L15','read_voltage','V'),('O16','cell_capacitance','fF'),('O17','wire_capacitance','fF')]:
        actual=float(cells[cell].find('s:v',ns).text)
        retained=source['cells']['New_Architecture'][cell]['value']
        assert actual==retained,(cell,actual,retained)
        supplied.append({'name':name,'value':actual,'unit':unit,'source':'New_Architecture!'+cell,'status':'supplied_Super_T_workbook_value'})
rows=[]
for board in (2,3,5,9,13,19):
    m=SizedParallelDatapathGoSimulation(board,1)
    c=m.memory.config;s=m.neural.schedule;p=load_sram_profile(memory_profile_name(board,'cacti_22nm_lstp'))
    assert c['sram_word_cycles']==p['sram_word_cycles']==2
    rows.append({'board':board,'arrays':m.neural.profile['arrays'],'memory':c,
        'iterations':board_hardware(board)['iterations'],'cycles_per_neural_evaluation':s['cycles'],
        'conversions_per_neural_evaluation':s['operations']['adc_conversions'],
        'readout_words_per_neural_evaluation':s['operations']['readout_words'],
        'adc_maximum_code':16*255,'adc_capacity':4095,'result_buffer_bits':1024,
        'candidate_buffer_bits':4096,'accumulator_bits':3072,'readout_bits_per_cycle':128,
        'sram_bits_per_word':32,'sram_cycles_per_word':2})
report={'workbook_sha256':source['source_sha256'],'supplied_values':supplied,'boards':rows,
 'assumptions':[
 'One custom 8-bit 1T1M cell per weight; 256 reliable levels not established by supplied workbook.',
 'Two physical custom arrays per board, H96 and three outputs; maximum 723x96. Long-line settling and wire drop require circuit validation.',
 'Sixteen rows active; ideal 12-bit ADC codes; 13 cycles per conversion group at assumed 500 MHz.',
 'Three-cycle array settling and one-cycle binary row drive are architectural assumptions, not per-size analog measurements.',
 'Mean input activity 0.5 and conductance 0.5; off-state current, programming and host Go costs excluded.',
 'Published native65 ADC area and event energy retained as macro budget, not replaced by NeuroSim.',
 'Digital area/dynamic scaling and native65 leakage are proxies; larger-board parent multiplier and bank-count router multiplier are estimates.',
 'Native22 CACTI SRAM/CAM; 1536 logical CAM entries cost a 2048-entry physical proxy; no extra ports.',
 'Physical allowance 15% of installed base area and 10% of digital dynamic energy; not extracted layout.'],
 'checks':{'xlsx_cached_values_match_retained_cells':True,'all_sram_services_match_characterization':True},
 'neurosim':'Existing p92 probe is selective cross-check only; no generic cell costs substituted.'}
(HERE/'hardware_audit.json').write_text(json.dumps(report,indent=2)+'\n')
print('Super-T values and six memory timing profiles verified')
