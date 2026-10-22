# SPDX-License-Identifier: MIT
# Source-native characterization only; never infer a library or target shrink.
set hardware_dir [file dirname [file dirname [file normalize [info script]]]]
set required_environment {IMC65_TARGET_DB IMC65_LIBRARY_NAME IMC65_CORNER IMC65_VOLTAGE_V IMC65_TEMPERATURE_C IMC65_DRIVING_CELL IMC65_LOAD_PF IMC65_OUT}
foreach name $required_environment {
    if {![info exists env($name)] || $env($name) eq ""} { error "Missing required characterization environment: $name" }
}
set target_db [file normalize $env(IMC65_TARGET_DB)]
if {![file readable $target_db]} { error "Unreadable foundry library: $target_db" }
set output_dir [file normalize $env(IMC65_OUT)]
if {[file exists $output_dir]} { error "Use a fresh output directory, preserving prior reports: $output_dir" }
set clock_period_ns 2.0
set clock_uncertainty_ns 0.05
set clock_transition_ns 0.1
set io_delay_ns 0.2
set rtl_files {}
set channel [open [file join $hardware_dir filelist.f] r]
foreach line [split [read $channel] "\n"] {
    if {[string trim $line] ne ""} {
        set rtl [file normalize [file join $hardware_dir [string trim $line]]]
        if {![file readable $rtl]} { error "Missing RTL: $rtl" }
        lappend rtl_files $rtl
    }
}
close $channel
set cases {
    {shift_add imc_shift_add_lane {}}
    {accumulator_bank imc_accumulator_bank {}}
    {accumulators8 imc_parallel_accumulators {}}
    {adc_result_banks imc_parallel_result_banks {}}
    {candidate_banks imc_candidate_banks {}}
    {ucb16 imc_ucb_batch16_overlap {}}
}
