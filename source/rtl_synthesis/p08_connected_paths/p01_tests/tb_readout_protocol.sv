// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_readout_protocol;
    logic clk=0, rst_n=0, clear=0, advance=1;
    logic capture_valid=0, capture_bank=0, capture_ready, capture_error;
    logic [5:0] capture_count=0;
    logic [511:0] capture_data=0;
    logic group_valid=0, group_ready, group_bank=0;
    logic [5:0] group_count=0;
    logic [6:0] column_base=0;
    logic [3:0] input_shift=0;
    logic rsp_valid, rsp_ready=0, rsp_error;
    logic [1:0] occupied;
    logic [31:0] read_addr=0;
    logic [255:0] read_data;
    logic debug_bus_valid, debug_release;
    logic [1:0] debug_bus_index;
    logic [127:0] debug_bus_data;
    logic [7:0] debug_bus_mask, debug_cmd_valid, debug_cmd_done, debug_cmd_error;
    logic [31:0] debug_cmd_addr;
    logic [95:0] debug_adc_code;
    integer n, i, k, seen_reads, seen_adds, beats;
    logic [511:0] data;
    imc_readout_path dut (.*);
    always #1 clk=~clk;
    task automatic tick; @(posedge clk); #0.1; endtask
    task automatic reset_all;
        @(negedge clk); rst_n=0; tick(); tick(); @(negedge clk); rst_n=1;
        if (occupied!==0 || rsp_valid) $fatal(1,"reset did not abort");
    endtask
    task automatic capture(input logic bank, input integer count);
        capture_bank=bank; capture_count=6'(count); capture_valid=1;
        capture_data='0;
        for (k=0;k<count;k=k+1) capture_data[k*16 +:16]=16'(k+1);
        #0.1; if (!capture_ready) $fatal(1,"capture not ready");
        tick(); @(negedge clk); capture_valid=0;
        if (capture_error) $fatal(1,"unexpected capture error");
    endtask
    task automatic start(input logic bank, input integer count);
        group_bank=bank; group_count=6'(count); group_valid=1;
        #0.1; if (!group_ready) $fatal(1,"group not ready");
        tick(); @(negedge clk); group_valid=0;
    endtask
    task automatic flush;
        clear=1; tick(); @(negedge clk); clear=0;
        if (occupied!==0 || rsp_valid || read_data!==0) $fatal(1,"clear did not flush");
    endtask
    initial begin
        reset_all();
        // Every partial group length, including both eight-lane and bus boundaries.
        for (n=1;n<=32;n=n+1) begin
            flush(); capture(0,n); column_base=7'd64; input_shift=4'd2;
            data=capture_data; start(0,n); capture_data='1;
            beats=(n+7)/8; seen_reads=1; seen_adds=0;
            while (!rsp_valid) begin
                advance=0; #0.1;
                if (debug_bus_valid || debug_cmd_valid!=0 || debug_release) $fatal(1,"stalled action");
                tick(); @(negedge clk);
                if (!occupied[0]) $fatal(1,"stall released bank");
                advance=1; #0.1;
                if (debug_bus_valid) begin
                    if (debug_bus_data!==data[int'(debug_bus_index)*128 +:128]) $fatal(1,"stored beat corrupted");
                    seen_reads=seen_reads+1;
                end
                if (debug_cmd_valid!=0) seen_adds=seen_adds+1;
                tick(); @(negedge clk);
            end
            if (rsp_error || seen_reads!=beats || seen_adds!=beats || occupied[0]) $fatal(1,"beat census");
            for (i=0;i<n;i=i+1) begin
                read_addr='0; read_addr[(i%8)*4 +:4]=4'((64+i)/8); #0.1;
                if (read_data[(i%8)*32 +:32]!==32'((i+1)*4)) $fatal(1,"partial sum %0d/%0d",n,i);
            end
            repeat (3) begin tick(); @(negedge clk); if (!rsp_valid || rsp_error) $fatal(1,"response hold"); end
            rsp_ready=1; tick(); @(negedge clk); rsp_ready=0;
        end
        flush(); capture(0,17); capture(1,3); column_base=0; input_shift=0;
        start(0,16);
        if (!rsp_valid || !rsp_error || occupied!==2'b11) $fatal(1,"metadata mismatch consumed bank");
        rsp_ready=1; tick(); @(negedge clk); rsp_ready=0;
        start(0,17); clear=1; tick(); @(negedge clk); clear=0;
        if (occupied!==0 || rsp_valid) $fatal(1,"clear while reading");
        capture(1,32); start(1,32);
        repeat (3) begin tick(); @(negedge clk); end
        if (debug_cmd_valid==0) $fatal(1,"not in add state");
        reset_all();
        capture(0,3); column_base=7'd1; start(0,3);
        if (!rsp_valid || !rsp_error || !occupied[0]) $fatal(1,"unaligned group accepted");
        flush(); capture_count=0; capture_valid=1; tick(); @(negedge clk); capture_valid=0;
        if (!capture_error || occupied!=0) $fatal(1,"invalid capture accepted");
        flush(); column_base=0; input_shift=11; read_addr=0;
        for (n=1;n<=257;n=n+1) begin
            capture_bank=0; capture_count=1; capture_data=512'd4095; capture_valid=1;
            tick(); @(negedge clk); capture_valid=0; start(0,1);
            tick(); @(negedge clk);
            if (!rsp_valid || rsp_error!==(n==257)) $fatal(1,"overflow status %0d",n);
            if (read_data[31:0]!==32'(8386560*((n<257)?n:256))) $fatal(1,"overflow modified sum");
            rsp_ready=1; tick(); @(negedge clk); rsp_ready=0;
        end
        capture_bank=0; capture_count=1; capture_data=0; capture_valid=1;
        tick(); @(negedge clk); capture_valid=0; start(0,1);
        tick(); @(negedge clk); if (!rsp_valid || rsp_error) $fatal(1,"stale overflow propagated");
        $display("tb_readout_protocol PASS partial_lengths=32 stalls clear reset invalid_metadata"); $finish;
    end
endmodule
