// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_connected_ucb;
    logic clk=0, rst_n=0;
    logic load_valid=0, load_ready, load_bank=0, word_valid=0, word_ready, load_error;
    logic [4:0] load_count=0;
    logic [31:0] child_id=0, header_word=0;
    logic dispatch_valid=0, dispatch_ready, dispatch_bank=0;
    logic [31:0] parent_visits=0;
    logic [63:0] exploration=0;
    logic rsp_valid, rsp_ready=0, rsp_error;
    logic [31:0] rsp_child;
    logic [63:0] rsp_score;
    logic [1:0] occupied;
    logic [15:0] debug_lane_active;
    logic [511:0] ids, visits;
    logic [1023:0] values;
    logic [31:0] expected_child;
    logic [63:0] expected_score;
    integer file, fields, target, count, i, j, started, cycle=0, batches=0, scores=0;
    string input_path, vcd_path;
    imc_selection_path dut (.*);
    always #1 clk=~clk;
    always @(posedge clk) cycle=cycle+1;
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
            fields=$fscanf(file,"%d %d %h %h %h %h %h %h %h\n",target,count,
                parent_visits,exploration,ids,visits,values,expected_child,expected_score);
            if (fields!=9 || count<1 || count>16) $fatal(1,"malformed row");
            load_bank=1'(batches%2); dispatch_bank=load_bank;
            load_count=5'(count); load_valid=1;
            #0.1; if (!load_ready) $fatal(1,"load blocked");
            tick(); @(negedge clk); load_valid=0;
            for (i=0;i<count;i=i+1) begin
                child_id=ids[i*32 +: 32];
                for (j=0;j<6;j=j+1) begin
                    word_valid=0; tick(); @(negedge clk); tick(); @(negedge clk);
                    word_valid=1;
                    case (j)
                        0: header_word=visits[i*32 +: 32];
                        1: header_word=values[i*64 +: 32];
                        2: header_word=values[i*64+32 +: 32];
                        default: header_word=32'hfeed0000+32'(j);
                    endcase
                    #0.1; if (!word_ready) $fatal(1,"header blocked");
                    tick(); @(negedge clk);
                end
                word_valid=0;
                repeat (4) begin tick(); @(negedge clk); end
            end
            // Destroy external operand buses before dispatch. Only stored bank data may score.
            ids='0; visits='0; values='0; child_id='0; header_word='0;
            dispatch_valid=1; #0.1;
            if (!dispatch_ready) $fatal(1,"bank not published");
            tick(); started=cycle;
            @(negedge clk); dispatch_valid=0;
            while (!rsp_valid) begin
                tick(); @(negedge clk);
                if (cycle-started>200) $fatal(1,"score timeout");
            end
            if (rsp_error || rsp_child!==expected_child || rsp_score!==expected_score)
                $fatal(1,"connected score mismatch batch=%0d child=%0d/%0d score=%h/%h",batches,rsp_child,expected_child,rsp_score,expected_score);
            if (cycle-started!=169+count) $fatal(1,"latency mismatch");
            repeat (3) begin
                tick(); @(negedge clk);
                if (!rsp_valid || !occupied[dispatch_bank] || rsp_score!==expected_score) $fatal(1,"response ownership lost");
            end
            rsp_ready=1; tick(); @(negedge clk); rsp_ready=0;
            if (occupied[dispatch_bank]) $fatal(1,"release failed");
            scores=scores+count; batches=batches+1;
        end
        $display("tb_connected_ucb PASS batches=%0d scores=%0d",batches,scores);
        $finish;
    end
endmodule
