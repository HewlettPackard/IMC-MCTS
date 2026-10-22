# Synopsys Design Compiler batch flow for the IMC-MCTS RTL handoff.
# Configuration is passed through environment variables by run_all.sh.

proc require_env {name} {
    if {![info exists ::env($name)] || $::env($name) eq ""} {
        error "Required environment variable $name is not set"
    }
    return $::env($name)
}

set project_dir [file normalize [require_env PROJECT_DIR]]
set run_name    [require_env RUN_NAME]
set top         [require_env TOP]
set params      $::env(PARAMS)
set sequential  [expr {$::env(SEQUENTIAL) eq "1"}]
set result_dir  [file join $project_dir results $run_name]

set target_db "/home/PDK/TSMC65/ARM/core_fb/db/sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c.db"
set target_library [list $target_db]
set link_library   [list "*" $target_db]
set_app_var search_path [list $project_dir]

file mkdir $result_dir
define_design_lib WORK -path [file join $result_dir work]

set fp [open [file join $project_dir filelist.f] r]
set rtl_files {}
foreach line [split [read $fp] "\n"] {
    set line [string trim $line]
    if {$line ne "" && ![string match "#*" $line]} {
        lappend rtl_files [file join $project_dir $line]
    }
}
close $fp

analyze -format sverilog $rtl_files
if {$params eq ""} {
    elaborate $top
} else {
    elaborate $top -parameters $params
}
# elaborate leaves the newly parameterized instance as the current design.
# Re-selecting by wildcard can accidentally match both it and its template.
link

redirect -file [file join $result_dir check_design_precompile.rpt] {check_design}

# Keep hierarchy available for the requested integrated area breakdown.
set_ungroup [get_designs *] false

set clock_period     2.0
set clock_uncertainty 0.05
set clock_transition  0.10
set io_delay           0.20
set output_load_pf     0.01
set driver_cell "BUF_X1M_A12TR"

set rst_ports [get_ports -quiet rst_n]
if {$sequential} {
    set clk_port [get_ports clk]
    create_clock -name clk -period $clock_period $clk_port
    set_clock_uncertainty $clock_uncertainty [get_clocks clk]
    set_clock_transition $clock_transition [get_clocks clk]
    set data_inputs [remove_from_collection [all_inputs] $clk_port]
    if {[sizeof_collection $data_inputs] > 0} {
        set_input_delay $io_delay -clock clk $data_inputs
        set_driving_cell -lib_cell $driver_cell -pin Y $data_inputs
    }
    if {[sizeof_collection [all_outputs]] > 0} {
        set_output_delay $io_delay -clock clk [all_outputs]
    }
} else {
    set_max_delay $clock_period -from [all_inputs] -to [all_outputs]
    if {[sizeof_collection [all_inputs]] > 0} {
        set_driving_cell -lib_cell $driver_cell -pin Y [all_inputs]
    }
}
if {[sizeof_collection [all_outputs]] > 0} {
    set_load $output_load_pf [all_outputs]
}
if {[sizeof_collection $rst_ports] > 0} {
    # rst_n is an active-low asynchronous reset; exclude reset assertion paths.
    set_false_path -from $rst_ports
}

write_sdc [file join $result_dir applied.sdc]

compile_ultra -no_autoungroup
set_fix_multiple_port_nets -all -buffer_constants

redirect -file [file join $result_dir check_design_postcompile.rpt] {check_design}
redirect -file [file join $result_dir area.rpt] {report_area -nosplit}
redirect -file [file join $result_dir area_hier.rpt] {report_area -hierarchy -nosplit}
redirect -file [file join $result_dir timing.rpt] {report_timing -delay_type max -max_paths 20 -nworst 3 -input_pins -nets -transition_time -capacitance -nosplit}
redirect -file [file join $result_dir constraints.rpt] {report_constraint -all_violators -nosplit}
redirect -file [file join $result_dir clocks.rpt] {report_clock -attributes -skew}
redirect -file [file join $result_dir cells.rpt] {report_reference -hierarchy -nosplit}
redirect -file [file join $result_dir resources.rpt] {report_resources -hierarchy -nosplit}
redirect -file [file join $result_dir power_vectorless.rpt] {report_power -analysis_effort high -nosplit}
redirect -file [file join $result_dir qor.rpt] {report_qor -nosplit}

change_names -rules verilog -hierarchy
write -format verilog -hierarchy -output [file join $result_dir mapped.v]
write -format ddc -hierarchy -output [file join $result_dir mapped.ddc]

set details [open [file join $result_dir run_details.txt] w]
puts $details "top=$top"
puts $details "parameters=$params"
puts $details "technology=TSMC 65nm"
puts $details "library=sc12_cln65gplus_base_rvt"
puts $details "corner=tt_typical_max_1p00v_25c"
puts $details "voltage=1.00 V"
puts $details "temperature=25 C"
puts $details "time_unit=1 ns"
puts $details "capacitance_unit=1 pF"
puts $details "area_unit=square micrometers"
puts $details "clock_period_ns=$clock_period"
puts $details "clock_uncertainty_ns=$clock_uncertainty"
puts $details "clock_transition_ns=$clock_transition"
puts $details "input_output_delay_ns=$io_delay"
puts $details "input_driver=$driver_cell/Y"
puts $details "output_load_pf=$output_load_pf"
puts $details "reset_exception=set_false_path -from rst_n (active-low asynchronous reset)"
puts $details "compile=compile_ultra -no_autoungroup"
puts $details "power=vectorless; no workload activity supplied"
puts $details "design_compiler=U-2022.12-SP7-1"
close $details

exit
