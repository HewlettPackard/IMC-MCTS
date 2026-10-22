#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT

"""
Generate LaTeX Tables for Ablation Studies with Citations
===========================================================

Generates publication-ready LaTeX tables with proper citations for all data sources.
"""

import pandas as pd
import numpy as np
import os


def generate_progressive_buildup_table_with_citations():
    """Generate Table 1: Progressive Optimization Build-up with citations"""

    print("\n" + "="*80)
    print("TABLE 1: PROGRESSIVE OPTIMIZATION BUILD-UP (WITH CITATIONS)")
    print("="*80)
    print()

    # Load data
    progressive_df = pd.read_csv('../../experiment_results/ablation_progressive_buildup.csv')
    progressive_9x9 = progressive_df[progressive_df['board_size'] == 9].copy()

    print("% Table 1: Progressive Optimization Build-up")
    print("% Data sources cited for transparency")
    print()
    print("\\begin{table*}[t]")
    print("\\centering")
    print("\\caption{Progressive Optimization Analysis for 9$\\times$9 Board. Data sources: ")
    print("ARM Cortex-M7 baseline from CMSIS-NN~\\cite{cmsis-nn}; ")
    print("Digital ASIC estimates from Eyeriss~\\cite{eyeriss} and DianNao~\\cite{dianNao}; ")
    print("IMC/TCAM/Hardware specs from our synthesis data @ 22nm.}")
    print("\\label{tab:progressive_buildup}")
    print("\\begin{tabular}{|l|r|r|r|r|l|}")
    print("\\hline")
    print("\\textbf{Configuration} & \\textbf{Speedup} & \\textbf{Energy} & \\textbf{Area} & \\textbf{TOPS/W} & \\textbf{Key Improvement} \\\\")
    print("                       & \\textbf{vs CPU}  & \\textbf{Savings}& \\textbf{(mm²)}& & \\\\")
    print("\\hline")

    # Add data with source annotations
    citations = {
        'Baseline': '~\\cite{cmsis-nn}',
        '+ Digital Selection': '~\\cite{eyeriss}',
        '+ TCAM Selection': '~(ours)',
        '+ Digital Rollout': '~\\cite{eyeriss,dianNao}',
        '+ IMC Rollout': '~(ours)',
        '+ Hardware Expansion': '~(ours)',
        'Full Accelerator': '~(ours)'
    }

    for _, row in progressive_9x9.iterrows():
        configuration_name = row['configuration_name']
        speedup = row['speedup_vs_baseline']
        energy = row['energy_savings_vs_baseline']
        area = row['area_mm2']
        tops_w = row['tops_per_watt']
        bottleneck = row['bottleneck']

        # Format area
        if area < 0.0001:
            area_str = "--"
        else:
            area_str = f"{area:.4f}"

        # Get configuration short name
        config_short = configuration_name.replace("(ARM CPU)", "").replace("(chosen)", "").strip()
        if len(config_short) > 25:
            config_short = config_short[:22] + "..."

        # Add citation
        citation = citations.get(config_short, '')
        config_with_cite = config_short + citation

        # Shorten bottleneck
        bottleneck_short = bottleneck
        if len(bottleneck_short) > 30:
            bottleneck_short = bottleneck_short[:27] + "..."

        print(f"{config_with_cite:40s} & {speedup:5.1f}$\\times$ & {energy:5.1f}$\\times$ & "
              f"{area_str:8s} & {tops_w:6.1f} & {bottleneck_short} \\\\")

    print("\\hline")
    print("\\end{tabular}")

    # Add table notes
    print("\\vspace{2mm}")
    print("\\begin{flushleft}")
    print("\\footnotesize")
    print("\\textit{Note}: Baseline from ARM Cortex-M7 @ 400 MHz running CMSIS-NN; ")
    print("Digital alternatives scaled from Eyeriss @ 65nm and DianNao @ 65nm to 22nm; ")
    print("IMC, TCAM, and optimized hardware from our synthesis results.")
    print("\\end{flushleft}")
    print("\\end{table*}")
    print()


def generate_design_alternatives_table_with_citations():
    """Generate Table 2: Design Alternative Comparisons with citations"""

    print("\n" + "="*80)
    print("TABLE 2: DESIGN ALTERNATIVE COMPARISONS (WITH CITATIONS)")
    print("="*80)
    print()

    # Load data
    alternatives_df = pd.read_csv('../../experiment_results/ablation_design_alternatives.csv')
    alternatives_9x9 = alternatives_df[alternatives_df['board_size'] == 9].copy()

    print("% Table 2: Design Alternative Comparisons")
    print("% All data sources cited")
    print()
    print("\\begin{table*}[t]")
    print("\\centering")
    print("\\caption{Module Implementation Alternatives for 9$\\times$9 Board. ")
    print("Baseline sources: ARM Cortex-M7~\\cite{cmsis-nn}, analytical models. ")
    print("Digital ASIC from Eyeriss~\\cite{eyeriss} (8.3 pJ/MAC @ 65nm, scaled to 22nm). ")
    print("FPGA estimates from literature~\\cite{fpga-survey}. ")
    print("Our designs (IMC, TCAM, Optimized) from synthesis @ 22nm.}")
    print("\\label{tab:design_alternatives}")
    print("\\begin{tabular}{|l|l|r|r|r|r|c|}")
    print("\\hline")
    print("\\textbf{Module} & \\textbf{Implementation} & \\textbf{Latency} & \\textbf{Energy} & \\textbf{Area} & \\textbf{Speedup} & \\textbf{Choice} \\\\")
    print("               &                         & \\textbf{(ns)}    & \\textbf{(pJ)}  & \\textbf{(mm²)}& \\textbf{vs Base}& \\\\")
    print("\\hline")

    # Citations for each implementation
    impl_citations = {
        'Software (ARM CPU)': '~\\cite{cmsis-nn}',
        'Digital ASIC': '~\\cite{eyeriss}',
        'FPGA': '~\\cite{fpga-survey}',
        'IMC Crossbar (chosen)': '~(ours)',
        'Sequential FSM': '~(analytical)',
        'Hash Table': '~(analytical)',
        'TCAM (chosen)': '~(ours)',
        'Software': '~\\cite{cmsis-nn}',
        'Digital Hardware': '~(analytical)',
        'Optimized (chosen)': '~(ours)'
    }

    modules = alternatives_9x9['module_name'].unique()

    for module_idx, module in enumerate(modules):
        module_df = alternatives_9x9[alternatives_9x9['module_name'] == module]

        for row_index, row in module_df.iterrows():
            implementation = row['implementation']
            latency = row['latency_per_op_ns']
            energy = row['energy_per_op_pj']
            area = row['area_mm2']
            speedup = row['speedup_vs_baseline']
            chosen = row['chosen']

            # Format area
            if area < 0.00001:
                area_str = "--"
            else:
                area_str = f"{area:.5f}"

            # Choice marker
            choice_mark = "\\checkmark" if chosen else ""

            # Module name only on first row
            if row_index == module_df.index[0]:
                module_name = module.replace("Unit", "")
            else:
                module_name = ""

            # Add citation
            citation = impl_citations.get(implementation, '')
            impl_with_cite = implementation + citation

            print(f"{module_name:15s} & {impl_with_cite:30s} & {latency:8.1f} & {energy:8.1f} & "
                  f"{area_str:8s} & {speedup:5.1f}$\\times$ & {choice_mark:10s} \\\\")

        # Add line between modules
        if module_idx < len(modules) - 1:
            print("\\hline")

    print("\\hline")
    print("\\end{tabular}")

    # Add table notes
    print("\\vspace{2mm}")
    print("\\begin{flushleft}")
    print("\\footnotesize")
    print("\\textit{Data sources}: ")
    print("\\textbf{Software}: ARM Cortex-M7 @ 400 MHz with CMSIS-NN~\\cite{cmsis-nn}. ")
    print("\\textbf{Digital ASIC}: Eyeriss @ 65nm (8.3 pJ/MAC)~\\cite{eyeriss} scaled to 22nm ($\\sim$4 pJ/MAC). ")
    print("\\textbf{FPGA}: Typical values from FPGA accelerator survey~\\cite{fpga-survey} (2-3$\\times$ slower, 5$\\times$ higher energy than ASIC). ")
    print("\\textbf{Analytical}: Estimated from typical digital logic @ 500 MHz, 22nm. ")
    print("\\textbf{Ours}: Aggregate synthesis-derived results normalized to a 22nm reference node.")
    print("\\end{flushleft}")
    print("\\end{table*}")
    print()


def generate_references_section():
    """Generate bibliography entries for all cited sources"""

    print("\n" + "="*80)
    print("BIBLIOGRAPHY ENTRIES")
    print("="*80)
    print()
    print("% Add these to your references section:")
    print()

    print("@inproceedings{cmsis-nn,")
    print("  author = {Lai, Liangzhen and Suda, Naveen and Chandra, Vikas},")
    print("  title = {{CMSIS-NN: Efficient Neural Network Kernels for Arm Cortex-M CPUs}},")
    print("  booktitle = {arXiv preprint arXiv:1801.06601},")
    print("  year = {2018}")
    print("}")
    print()

    print("@inproceedings{eyeriss,")
    print("  author = {Chen, Yu-Hsin and Emer, Joel and Sze, Vivienne},")
    print("  title = {{Eyeriss: A Spatial Architecture for Energy-Efficient Dataflow for Convolutional Neural Networks}},")
    print("  booktitle = {Proceedings of the 43rd International Symposium on Computer Architecture (ISCA)},")
    print("  year = {2016},")
    print("  pages = {367--379}")
    print("}")
    print()

    print("@inproceedings{dianNao,")
    print("  author = {Chen, Tianshi and Du, Zidong and Sun, Ninghui and Wang, Jia and Wu, Chengyong and Chen, Yunji and Temam, Olivier},")
    print("  title = {{DianNao: A Small-Footprint High-Throughput Accelerator for Ubiquitous Machine-Learning}},")
    print("  booktitle = {Proceedings of the 19th International Conference on Architectural Support for Programming Languages and Operating Systems (ASPLOS)},")
    print("  year = {2014},")
    print("  pages = {269--284}")
    print("}")
    print()

    print("@article{fpga-survey,")
    print("  author = {Nurvitadhi, Eriko and Venkatesh, Ganesh and Sim, Jaewoong and Marr, Debbie and Huang, Randy and Ong Gee Hock, Jason and Liew, Yeong Tat and Srivatsan, Krishnan and Moss, Duncan and Subhaschandra, Suchit and others},")
    print("  title = {{Can FPGAs Beat GPUs in Accelerating Next-Generation Deep Neural Networks?}},")
    print("  journal = {Proceedings of the 2017 ACM/SIGDA International Symposium on Field-Programmable Gate Arrays},")
    print("  year = {2017},")
    print("  pages = {5--14}")
    print("}")
    print()

    print("% Alternative FPGA citation:")
    print("@article{fpga-nn-survey,")
    print("  author = {Guo, Kaiyuan and Zeng, Shulin and Yu, Jincheng and Wang, Yu and Yang, Huazhong},")
    print("  title = {{A Survey of FPGA-Based Neural Network Inference Accelerators}},")
    print("  journal = {ACM Transactions on Reconfigurable Technology and Systems},")
    print("  year = {2019},")
    print("  volume = {12},")
    print("  number = {1},")
    print("  pages = {1--26}")
    print("}")
    print()

    print("% Additional useful references:")
    print()
    print("@inproceedings{tpu,")
    print("  author = {Jouppi, Norman P. and Young, Cliff and Patil, Nishant and Patterson, David and Agrawal, Gaurav and Bajwa, Raminder and Bates, Sarah and Bhatia, Suresh and Boden, Nan and Borchers, Al and others},")
    print("  title = {{In-Datacenter Performance Analysis of a Tensor Processing Unit}},")
    print("  booktitle = {Proceedings of the 44th Annual International Symposium on Computer Architecture (ISCA)},")
    print("  year = {2017},")
    print("  pages = {1--12}")
    print("}")
    print()


def main():
    """Generate all tables with citations"""

    print("\n" + "="*80)
    print("LATEX TABLES WITH CITATIONS FOR ABLATION STUDIES")
    print("="*80)
    print()
    print("Complete tables with all data sources properly cited")
    print("="*80)

    # Check if data files exist
    prog_file = '../../experiment_results/ablation_progressive_buildup.csv'
    alt_file = '../../experiment_results/ablation_design_alternatives.csv'

    if not os.path.exists(prog_file):
        print(f"\n❌ Error: {prog_file} not found!")
        print("   Run ablation_progressive_buildup.py first")
        return

    if not os.path.exists(alt_file):
        print(f"\n❌ Error: {alt_file} not found!")
        print("   Run ablation_design_alternatives.py first")
        return

    # Generate tables with citations
    generate_progressive_buildup_table_with_citations()
    generate_design_alternatives_table_with_citations()
    generate_references_section()

    print("\n" + "="*80)
    print("✅ LaTeX tables with citations generated successfully!")
    print("="*80)
    print()
    print("Usage:")
    print("1. Copy the table code above into your LaTeX document")
    print("2. Copy the bibliography entries to your .bib file")
    print("3. Ensure packages: \\usepackage{multirow,array,cite}")
    print()


if __name__ == "__main__":
    main()
