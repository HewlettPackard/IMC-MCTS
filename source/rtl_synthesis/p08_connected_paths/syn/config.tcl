# SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
# SPDX-License-Identifier: MIT
set flow_root [file normalize [file join [file dirname [info script]] ..]]
set design_list {imc_selection_path imc_readout_path}
set rtl_files {}
set fh [open [file join $flow_root filelist.f] r]
foreach line [split [read $fh] "\n"] {
    if {[string trim $line] ne ""} {lappend rtl_files [file normalize [file join $flow_root $line]]}
}
close $fh
set clock_period_ns 2.0
set io_delay_ns 0.2
if {![info exists ::env(TARGET_DB)]} {error "Set TARGET_DB to the same native 65 nm library/corner used for p07"}
set target_library [list $::env(TARGET_DB)]
set link_library [concat * $target_library]
