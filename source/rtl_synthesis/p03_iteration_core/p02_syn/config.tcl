# SPDX-License-Identifier: MIT
# Required library information is supplied by the authorized 65 nm environment.
# This file also runs in tclsh to check inputs before starting Design Compiler.
foreach name {IMC65_TARGET_DB IMC65_LIBRARY_NAME IMC65_CORNER IMC65_VOLTAGE_V IMC65_TEMPERATURE_C IMC65_DRIVING_CELL IMC65_LOAD_PF IMC65_OUT} {
    if {![info exists env($name)] || $env($name) eq ""} {
        error "Missing $name; no technology defaults or legacy costs are substituted"
    }
}
set target_db [file normalize $env(IMC65_TARGET_DB)]
if {![file isfile $target_db] || ![file readable $target_db] || [file extension $target_db] ne ".db"} {
    error "IMC65_TARGET_DB must name a readable compiled 65 nm library"
}
foreach name {IMC65_VOLTAGE_V IMC65_TEMPERATURE_C IMC65_LOAD_PF} {
    if {![string is double -strict $env($name)] || [regexp -nocase {nan|inf} $env($name)]} {
        error "$name must be finite and numeric"
    }
}
if {$env(IMC65_VOLTAGE_V) <= 0 || $env(IMC65_LOAD_PF) <= 0} {
    error "Supply voltage and output load must be positive"
}
set output_dir [file normalize $env(IMC65_OUT)]
if {[file exists $output_dir]} {
    error "IMC65_OUT already exists; use a new UTC run directory"
}
set hardware_dir [file dirname [file dirname [file normalize [info script]]]]
set source_node_nm 65
set target_node_nm 22
set clock_period_ns 2.0
set clock_uncertainty_ns 0.05
set io_delay_ns 0.2
set clock_transition_ns 0.1
set rtl_files {}
set filelist [open [file join $hardware_dir filelist.f] r]
foreach line [split [read $filelist] "\n"] {
    if {[string trim $line] ne ""} { lappend rtl_files [file join $hardware_dir [string trim $line]] }
}
close $filelist
set cases {
    {tree_update imc_tree_update {BOARD_SIZE=9,CAM_ENTRIES=1024,NEURAL_BYTES=16512}}
    {ucb_score imc_ucb_score {}}
    {complete_core imc_iteration_core {BOARD_SIZE=9,CAM_ENTRIES=1024,HIDDEN=96}}
}
