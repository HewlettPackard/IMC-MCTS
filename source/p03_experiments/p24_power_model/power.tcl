# Re-analyze an existing native DDC with its own mapped-netlist activity.
proc required {name} {
    if {![info exists ::env($name)] || $::env($name) eq ""} {error "Set $name"}
    return $::env($name)
}
set target_library [list [required IMC65_TARGET_DB]]
set link_library [concat "*" $target_library]
set native [required IMC_POWER_NATIVE]
set out [required IMC_POWER_OUT]
read_ddc [file join $native mapped.ddc]
current_design [required IMC_POWER_DESIGN]
link
set expected_lib sc12_cln65gplus_base_rvt_tt_typical_max_1p00v_25c
if {[sizeof_collection [get_libs -quiet $expected_lib]] != 1} {error "Library differs from the returned TSMC65 reports"}
set_operating_conditions -library $expected_lib tt_typical_max_1p00v_25c
read_sdc [file join $native applied.sdc]
redirect -file [file join $out units.rpt] {report_units}
redirect -file [file join $out library.rpt] {
    foreach_in_collection library [get_libs *] {report_lib [get_object_name $library]}
}
redirect -file [file join $out check_design.rpt] {check_design}
redirect -file [file join $out activity_read.rpt] {
    read_saif -input [file join $out activity.saif] -instance_name [required IMC_POWER_SCOPE]
}
redirect -file [file join $out activity_coverage.rpt] {report_saif}
redirect -file [file join $out power_annotated.rpt] {report_power -analysis_effort high -nosplit}
redirect -file [file join $out power_hierarchy.rpt] {report_power -hierarchy -analysis_effort high -nosplit}
redirect -file [file join $out area.rpt] {report_area -nosplit}
redirect -file [file join $out timing.rpt] {report_timing -delay_type max -max_paths 20 -nosplit}
set fp [open [file join $out scope.txt] w]
puts $fp "native_node_nm=65"
puts $fp "source_ddc=$native/mapped.ddc"
puts $fp "activity_scope=[required IMC_POWER_SCOPE]"
puts $fp "method=zero-delay mapped module replay, full core-cycle window including idle clocks"
puts $fp "admission=pending coverage, units, PVT and workload review; no 22nm conversion performed"
close $fp
exit
