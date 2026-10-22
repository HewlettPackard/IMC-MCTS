// Arithmetic vectors, changing inputs while busy, held results and reset.
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_arithmetic;
    logic clk=0, rst_n=0;
    logic score_req_valid=0, score_req_ready;
    logic [31:0] score_parent_visits=0, score_child_visits=0;
    logic [63:0] score_child_value=0, score_exploration=0;
    logic score_rsp_valid, score_rsp_ready=0, score_rsp_error;
    logic [63:0] score_rsp_value;
    logic [3:0] debug_state;
    logic [319:0] vectors [0:4095], vector;
    string path, event_path;
    integer count,i,cycle=0,started,events;
    imc_ucb_score dut (.*);
    always #5 clk=~clk;
    always @(posedge clk) cycle=cycle+1;
    task automatic tick;
        @(posedge clk); #1;
    endtask
    initial begin
        if (!$value$plusargs("VECTORS=%s",path) || !$value$plusargs("COUNT=%d",count) ||
            !$value$plusargs("EVENTS=%s",event_path)) $fatal(1,"missing vectors/count/events");
        $readmemh(path,vectors,0,count-1); events=$fopen(event_path,"w");
        tick(); tick(); @(negedge clk); rst_n=1;
        for(i=0;i<count;i=i+1) begin
            vector=vectors[i];
            @(negedge clk);
            {score_parent_visits,score_child_visits,score_child_value,score_exploration}=vector[319:128];
            score_req_valid=1; #1; if(!score_req_ready) $fatal(1,"not ready");
            tick(); started=cycle;
            @(negedge clk); score_req_valid=0;
            score_parent_visits=0; score_child_visits=0; score_child_value='1; score_exploration='1;
            while(!score_rsp_valid) tick();
            if(score_rsp_error!==vector[0] || (!vector[0] && score_rsp_value!==vector[127:64]))
                $fatal(1,"vector %0d actual=%h error=%0d expected=%h error=%0d",i,score_rsp_value,score_rsp_error,vector[127:64],vector[0]);
            $fdisplay(events,"score,%0d,%0d,%016x,%0d",i,cycle-started,score_rsp_value,score_rsp_error);
            repeat(3) begin tick(); if(!score_rsp_valid || score_req_ready) $fatal(1,"completion not held"); end
            @(negedge clk); score_rsp_ready=1; tick(); @(negedge clk); score_rsp_ready=0;
        end
        @(negedge clk); score_parent_visits=2; score_child_visits=1; score_child_value=0;
        score_exploration=64'h3ff0000000000000; score_req_valid=1;
        tick(); @(negedge clk); score_req_valid=0; repeat(20) tick();
        @(negedge clk); rst_n=0; tick();
        if(score_rsp_valid || score_req_ready) $fatal(1,"reset did not abort");
        @(negedge clk); rst_n=1; tick(); if(!score_req_ready) $fatal(1,"reset not ready");
        $display("tb_imc_arithmetic PASS vectors=%0d",count); $fclose(events); $finish;
    end
endmodule
