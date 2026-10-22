// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_selection_protocol;
    logic clk=0, rst_n=0;
    logic load_valid=0, load_ready, load_bank=0, word_valid=0, word_ready, load_error;
    logic [4:0] load_count=0;
    logic [31:0] child_id=0, header_word=0;
    logic dispatch_valid=0, dispatch_ready, dispatch_bank=0;
    logic [31:0] parent_visits=32'd10;
    logic [63:0] exploration=64'h3ff0000000000000;
    logic rsp_valid, rsp_ready=0, rsp_error;
    logic [31:0] rsp_child;
    logic [63:0] rsp_score, saved_score;
    logic [1:0] occupied;
    logic [15:0] debug_lane_active;
    integer i;
    imc_selection_path dut (.*);
    always #1 clk=~clk;
    task automatic tick; @(posedge clk); #0.1; endtask
    task automatic begin_load(input logic bank, input integer count);
        load_bank=bank; load_count=5'(count); load_valid=1; #0.1;
        if (!load_ready) $fatal(1,"begin blocked");
        tick(); @(negedge clk); load_valid=0;
    endtask
    task automatic finish_child(input integer id);
        child_id=32'(id);
        for (i=0;i<6;i=i+1) begin
            word_valid=0; tick(); @(negedge clk);
            if (i==0) header_word=1; else header_word=0;
            word_valid=1; #0.1; if (!word_ready) $fatal(1,"word blocked");
            tick(); @(negedge clk);
        end
        word_valid=0; header_word='1; child_id='1;
    endtask
    initial begin
        tick(); tick(); @(negedge clk); rst_n=1;
        begin_load(0,0);
        if (!load_error || occupied!=0) $fatal(1,"zero count allocated");
        begin_load(0,17);
        if (!load_error || occupied!=0) $fatal(1,"oversized count allocated");
        begin_load(0,1); dispatch_bank=0; #0.1;
        if (dispatch_ready) $fatal(1,"partial header published");
        finish_child(101); dispatch_valid=1; #0.1;
        if (!dispatch_ready) $fatal(1,"published group blocked");
        tick(); @(negedge clk); dispatch_valid=0;
        begin_load(1,1); finish_child(202);
        if (occupied!==2'b11) $fatal(1,"overlap failed");
        load_bank=0; dispatch_bank=1; #0.1;
        if (load_ready || dispatch_ready) $fatal(1,"owned resource advertised ready");
        repeat (190) begin tick(); @(negedge clk); end
        if (!rsp_valid || rsp_error || rsp_child!=101) $fatal(1,"first group changed");
        saved_score=rsp_score;
        repeat (4) begin tick(); @(negedge clk); if (!rsp_valid || rsp_score!==saved_score || occupied!=3) $fatal(1,"response lost ownership"); end
        rsp_ready=1; tick(); @(negedge clk); rsp_ready=0;
        if (occupied!==2'b10) $fatal(1,"wrong bank released");
        dispatch_valid=1; #0.1; if (!dispatch_ready) $fatal(1,"second group blocked");
        tick(); @(negedge clk); dispatch_valid=0;
        rst_n=0; tick(); tick(); @(negedge clk); rst_n=1;
        if (occupied!=0 || rsp_valid || debug_lane_active!=0) $fatal(1,"reset did not abort score");
        begin_load(1,1); finish_child(303);
        $display("tb_selection_protocol PASS loader_stalls bank_overlap ownership invalid_count reset"); $finish;
    end
endmodule
