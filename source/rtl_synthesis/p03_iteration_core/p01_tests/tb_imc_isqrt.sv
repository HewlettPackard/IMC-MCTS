// Check integer roots at squares, adjacent inputs and the full input range.
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_isqrt;
    logic clk=0, rst_n=0, clear=0, start=0, ready, done;
    logic [103:0] radicand=0;
    logic [51:0] root;
    logic [159:0] vectors [0:1023];
    string path;
    integer count,i,steps;
    imc_isqrt dut (.*);
    always #5 clk=~clk;
    task automatic tick;
        @(posedge clk); #1;
    endtask
    initial begin
        if(!$value$plusargs("VECTORS=%s",path) || !$value$plusargs("COUNT=%d",count)) $fatal(1,"missing vectors/count");
        $readmemh(path,vectors,0,count-1);
        tick(); tick(); @(negedge clk); rst_n=1;
        for(i=0;i<count;i=i+1) begin
            @(negedge clk); radicand=vectors[i][159:56]; start=1;
            tick(); @(negedge clk); start=0; radicand='1;
            steps=0;
            while(!done) begin tick(); steps=steps+1; end
            if(root!==vectors[i][55:4] || steps!=52) $fatal(1,"root/cycles differ at %0d",i);
        end
        @(negedge clk); start=1; tick(); @(negedge clk); start=0;
        repeat(7) tick(); @(negedge clk); clear=1; tick();
        if(root!=0 || done) $fatal(1,"clear failed");
        @(negedge clk); clear=0; tick(); if(!ready) $fatal(1,"clear not ready");
        $display("tb_imc_isqrt PASS vectors=%0d",count); $finish;
    end
endmodule
