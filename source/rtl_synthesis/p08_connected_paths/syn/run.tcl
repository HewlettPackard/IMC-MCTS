# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
source [file join [file dirname [info script]] config.tcl]
set reports [file join $flow_root syn reports]
file mkdir $reports
analyze -format sverilog $rtl_files
foreach design $design_list {
    elaborate $design
    current_design $design
    link
    create_clock -name clk -period $clock_period_ns [get_ports clk]
    set data_inputs [remove_from_collection [all_inputs] [get_ports {clk rst_n}]]
    set_input_delay $io_delay_ns -clock clk $data_inputs
    set_output_delay $io_delay_ns -clock clk [all_outputs]
    set_false_path -from [get_ports rst_n]
    redirect [file join $reports $design.pre_check.rpt] {check_design}
    compile_ultra
    redirect [file join $reports $design.check.rpt] {check_design}
    redirect [file join $reports $design.area.rpt] {report_area -hierarchy}
    redirect [file join $reports $design.timing.rpt] {report_timing -max_paths 20}
    redirect [file join $reports $design.constraints.rpt] {report_constraint -all_violators}
    redirect [file join $reports $design.qor.rpt] {report_qor}
    redirect [file join $reports $design.power_vectorless.rpt] {report_power -hierarchy}
    write -format verilog -hierarchy -output [file join $reports $design.netlist.v]
    write_sdc [file join $reports $design.sdc]
    remove_design $design
}
