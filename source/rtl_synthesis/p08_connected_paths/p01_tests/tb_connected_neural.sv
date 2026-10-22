// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_connected_neural;
    logic clk=0, rst_n=0, clear=0, advance=1;
    logic capture_valid=0, capture_bank=0, capture_ready, capture_error;
    logic [5:0] capture_count=0;
    logic [511:0] capture_data=0;
    logic group_valid=0, group_ready, group_bank=0;
    logic [5:0] group_count=0;
    logic [6:0] column_base=0;
    logic [3:0] input_shift=0;
    logic rsp_valid, rsp_ready=1, rsp_error;
    logic [1:0] occupied;
    logic [31:0] read_addr=0;
    logic [255:0] read_data;
    logic debug_bus_valid, debug_release;
    logic [1:0] debug_bus_index;
    logic [127:0] debug_bus_data;
    logic [7:0] debug_bus_mask, debug_cmd_valid, debug_cmd_done, debug_cmd_error;
    logic [31:0] debug_cmd_addr;
    logic [95:0] debug_adc_code;
    logic expected_bus, expected_release;
    logic [1:0] expected_index;
    logic [127:0] expected_bus_data;
    logic [7:0] expected_mask, expected_cmd;
    logic [31:0] expected_addr;
    logic [95:0] expected_codes;
    logic [255:0] expected_sums;
    integer file, fields, target, cycle=0, captures=0, reads=0, commands=0, i;
    string input_path, vcd_path;
    imc_readout_path dut (.*);
    always #1 clk=~clk;
    task automatic tick;
        @(posedge clk); #0.1;
    endtask
    initial begin
        if (!$value$plusargs("INPUT=%s",input_path)) $fatal(1,"need INPUT");
        if ($value$plusargs("VCD=%s",vcd_path)) begin
            $dumpfile(vcd_path); $dumpvars(0,dut);
        end
        file=$fopen(input_path,"r");
        if (file==0) $fatal(1,"cannot read input");
        tick(); tick(); @(negedge clk); rst_n=1;
        while (!$feof(file)) begin
            fields=$fscanf(file,"%d %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h %h\n",
                target,clear,capture_valid,capture_bank,capture_count,capture_data,
                group_valid,group_bank,group_count,column_base,input_shift,
                expected_bus,expected_index,expected_bus_data,expected_mask,
                expected_cmd,expected_addr,expected_codes,expected_sums,expected_release);
            if (fields!=20 || target!=cycle) $fatal(1,"malformed row");
            read_addr=expected_addr;
            #0.1;
            if (capture_valid && !capture_ready) $fatal(1,"capture blocked");
            if (group_valid && !group_ready) $fatal(1,"consume blocked cycle=%0d",cycle);
            if (debug_bus_valid!==expected_bus || debug_cmd_valid!==expected_cmd || debug_release!==expected_release)
                $fatal(1,"schedule mismatch cycle=%0d bus=%b/%b cmd=%h/%h release=%b/%b",cycle,
                    debug_bus_valid,expected_bus,debug_cmd_valid,expected_cmd,debug_release,expected_release);
            if (expected_bus && (debug_bus_index!==expected_index || debug_bus_data!==expected_bus_data || debug_bus_mask!==expected_mask))
                $fatal(1,"stored bus data mismatch cycle=%0d",cycle);
            if (expected_cmd && (debug_cmd_addr!==expected_addr || debug_adc_code!==expected_codes))
                $fatal(1,"staged command mismatch cycle=%0d",cycle);
            tick();
            if (capture_error || debug_cmd_error!=0 || (rsp_valid && rsp_error)) $fatal(1,"path error cycle=%0d",cycle);
            for (i=0;i<8;i=i+1) if (expected_cmd[i]) begin
                if (!debug_cmd_done[i] || read_data[i*32 +: 32]!==expected_sums[i*32 +: 32])
                    $fatal(1,"integer sum mismatch cycle=%0d lane=%0d",cycle,i);
                commands=commands+1;
            end
            if (expected_bus) reads=reads+1;
            if (capture_valid) captures=captures+1;
            cycle=cycle+1; @(negedge clk);
        end
        if (occupied!=0 || captures!=81 || reads!=180 || commands!=1200) $fatal(1,"census/ownership mismatch");
        $display("tb_connected_neural PASS captures=%0d reads=%0d commands=%0d edge_rows=%0d",captures,reads,commands,cycle);
        $finish;
    end
endmodule
