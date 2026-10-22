# SPDX-License-Identifier: MIT
# Optional future characterization contract. No DC run is part of this revision.
set hardware_dir [file dirname [file dirname [file normalize [info script]]]]
set top imc_ucb_batch_overlap
set ppa_role four_overlapped_UCB_parents_plus_unchanged_batch_dispatch
set source_node_nm 65
set target_node_nm 22
set clock_period_ns 2.0
set clock_uncertainty_ns 0.05
set clock_transition_ns 0.1
set io_delay_ns 0.2
set rst_port rst_n
set reset_is_async true
set flatten_hierarchy false
set parameters {}
set rtl_files {}
set channel [open [file join $hardware_dir filelist.f] r]
foreach line [split [read $channel] "\n"] {
    if {[string trim $line] ne ""} {
        set rtl [file normalize [file join $hardware_dir [string trim $line]]]
        if {![file readable $rtl]} { error "Missing source: $rtl" }
        lappend rtl_files $rtl
    }
}
close $channel
set required_environment {IMC65_TARGET_DB IMC65_LIBRARY_NAME IMC65_CORNER IMC65_VOLTAGE_V IMC65_TEMPERATURE_C IMC65_DRIVING_CELL IMC65_LOAD_PF IMC65_OUT}
# A future authorized DC driver must validate these inputs and use a fresh output
# directory before elaborating. There is deliberately no guessed technology.
set area_accounting "Inclusive wrapper includes four UCB scorers. Request exclusive wrapper overhead and per-child inclusive areas; never add inclusive wrapper plus children."
