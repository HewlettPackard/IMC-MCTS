# Synthesize only the projected orchestration block; child modules are ports.
proc required {name} {
    if {![info exists ::env($name)] || $::env($name) eq ""} {error "Set $name"}
    return $::env($name)
}
set target_library [list [required IMC65_TARGET_DB]]
set link_library [concat "*" $target_library]
set packet [file dirname [file dirname [file normalize [info script]]]]
set top [required IMC_GLUE_TOP]
if {$top ni {imc_iteration_glue imc_buffered_iteration_glue}} {error "Unknown glue top"}
set out [file normalize [required IMC_GLUE_OUT]]
if {[file exists $out]} {error "Use a new result directory"}
file mkdir $out
define_design_lib WORK -path [file join $out work]
analyze -format sverilog [file join $packet p04_glue $top.sv]
elaborate $top
link
set expected_lib sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c
if {[sizeof_collection [get_libs -quiet $expected_lib]] != 1} {error "Library differs from the returned TSMC65 reports"}
set_operating_conditions -library $expected_lib tt_typical_max_1p00v_25c
create_clock -name clk -period 2.0 [get_ports clk]
set_clock_uncertainty 0.05 [get_clocks clk]
set_clock_transition 0.1 [get_clocks clk]
set data [remove_from_collection [all_inputs] [get_ports clk]]
set_input_delay 0.2 -clock clk $data
set_driving_cell -lib_cell BUF_X1M_A12TR -pin Y $data
set_output_delay 0.2 -clock clk [all_outputs]
set_load 0.01 [all_outputs]
set_false_path -from [get_ports rst_n]
redirect -file [file join $out check_design_precompile.rpt] {check_design}
compile_ultra -no_autoungroup
set_fix_multiple_port_nets -all -buffer_constants
redirect -file [file join $out check_design_postcompile.rpt] {check_design}
redirect -file [file join $out units.rpt] {report_units}
redirect -file [file join $out area.rpt] {report_area -nosplit}
redirect -file [file join $out qor.rpt] {report_qor}
redirect -file [file join $out constraints.rpt] {report_constraint -all_violators -nosplit}
redirect -file [file join $out timing.rpt] {report_timing -delay_type max -max_paths 20 -nosplit}
redirect -file [file join $out power_vectorless.rpt] {report_power -analysis_effort high -nosplit}
write_sdc [file join $out applied.sdc]
change_names -rules verilog -hierarchy
write -format verilog -hierarchy -output [file join $out mapped.v]
write -format ddc -hierarchy -output [file join $out mapped.ddc]
exit
