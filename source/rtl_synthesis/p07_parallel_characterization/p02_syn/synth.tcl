# SPDX-License-Identifier: MIT
source [file join [file dirname [file normalize [info script]]] config.tcl]
file mkdir $output_dir
set_app_var target_library [list $target_db]
set_app_var link_library [concat * [list $target_db]]
set_app_var search_path [concat $search_path [file dirname $target_db]]

foreach case $cases {
    lassign $case label top parameters
    set case_dir [file join $output_dir $label]
    file mkdir $case_dir
    remove_design -all
    define_design_lib WORK -path [file join $case_dir work]
    analyze -format sverilog $rtl_files
    if {$parameters eq ""} { elaborate $top } else { elaborate $top -parameters $parameters }
    current_design $top
    link
    if {![check_design]} { error "$label: check_design failed before synthesis" }
    set_operating_conditions $env(IMC65_CORNER) -library $env(IMC65_LIBRARY_NAME)
    if {[sizeof_collection [get_ports -quiet clk]] != 0} {
        create_clock -name core_clk -period $clock_period_ns [get_ports clk]
        set_clock_uncertainty $clock_uncertainty_ns [get_clocks core_clk]
        set_clock_transition $clock_transition_ns [get_clocks core_clk]
        set data_inputs [remove_from_collection [all_inputs] [get_ports {clk rst_n}]]
        set_input_delay $io_delay_ns -clock core_clk $data_inputs
        set_output_delay $io_delay_ns -clock core_clk [all_outputs]
        set_false_path -from [get_ports rst_n]
    } else {
        set data_inputs [all_inputs]
        set_max_delay $clock_period_ns -from [all_inputs] -to [all_outputs]
    }
    set_driving_cell -library $env(IMC65_LIBRARY_NAME) -lib_cell $env(IMC65_DRIVING_CELL) $data_inputs
    set_load $env(IMC65_LOAD_PF) [all_outputs]
    compile_ultra
    if {![check_design]} { error "$label: check_design failed after synthesis" }
    redirect -file [file join $case_dir units.rpt] { report_units }
    redirect -file [file join $case_dir library.rpt] { report_lib $env(IMC65_LIBRARY_NAME) }
    redirect -file [file join $case_dir design.rpt] { report_design }
    redirect -file [file join $case_dir area.rpt] { report_area -hierarchy }
    redirect -file [file join $case_dir timing.rpt] { report_timing -max_paths 20 }
    redirect -file [file join $case_dir constraints.rpt] { report_constraint -all_violators }
    redirect -file [file join $case_dir timing_checks.rpt] { check_timing }
    redirect -file [file join $case_dir cells.rpt] { report_reference -hierarchy }
    redirect -file [file join $case_dir resources.rpt] { report_resources -hierarchy }
    redirect -file [file join $case_dir vectorless_power.rpt] { report_power -hierarchy }
    set fp [open [file join $case_dir run_details.txt] w]
    puts $fp "top=$top source_node_nm=65 clock_ns=$clock_period_ns io_delay_ns=$io_delay_ns"
    puts $fp "library=$target_db corner=$env(IMC65_CORNER) voltage_v=$env(IMC65_VOLTAGE_V) temperature_c=$env(IMC65_TEMPERATURE_C)"
    puts $fp "Power is vectorless until workload-matched gate-level activity and annotation coverage are verified. Do not adopt as calibrated energy."
    close $fp
    write -format verilog -hierarchy -output [file join $case_dir netlist.v]
    write_sdc [file join $case_dir constraints.sdc]
    write -format ddc -hierarchy -output [file join $case_dir design.ddc]
}
set fp [open [file join $output_dir STATUS.txt] w]
puts $fp "65 nm area/timing reports require library, units, corner and constraint review before adoption."
puts $fp "No physical power result: matching gate-level workload activity and annotation coverage remain required."
puts $fp "The arithmetic-only RTL VCD is not a power workload. No 65-to-22 nm conversion is performed here."
close $fp
exit
