// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_parallel_result_banks;
    logic clk=0, rst_n=0, clear=0, capture_valid=0, capture_bank=0;
    logic [5:0] capture_count=0;
    logic [511:0] capture_data=0;
    logic capture_ready, capture_error, release_valid=0, release_bank=0, read_bank=0;
    logic [1:0] read_index=0, occupied;
    logic [127:0] read_data;
    logic [7:0] read_slots_valid;
    integer i;
    imc_parallel_result_banks dut (.*);
    always #5 clk=~clk;
    task automatic tick; @(posedge clk); #1; endtask
    initial begin
        tick(); tick(); @(negedge clk); rst_n=1; capture_valid=1; capture_count=32;
        for (i=0;i<32;i=i+1) capture_data[i*16 +: 16]=16'(i+100);
        tick();
        if (occupied !== 1 || capture_error) $fatal(1,"capture bank zero");
        @(negedge clk); capture_valid=0;
        for (i=0;i<4;i=i+1) begin
            read_index=2'(i); #1;
            if (read_slots_valid !== 8'hff || read_data[15:0] !== 16'(100+8*i)) $fatal(1,"128-bit beat");
        end
        if (occupied !== 1) $fatal(1,"readout released bank before accumulation");
        capture_bank=1; capture_count=3; capture_valid=1; tick();
        if (occupied !== 3 || capture_error) $fatal(1,"second bank overlap");
        @(negedge clk); capture_bank=0; capture_data='1; tick();
        if (!capture_error || occupied !== 3) $fatal(1,"overwrite not rejected");
        @(negedge clk); capture_valid=0; read_bank=1; read_index=0; #1;
        if (read_slots_valid !== 8'h07 || read_data[127:48] !== 0) $fatal(1,"partial beat padding");
        release_valid=1; release_bank=0; tick();
        if (occupied !== 2) $fatal(1,"release ownership");
        @(negedge clk); release_valid=0; capture_bank=0; capture_valid=1; capture_count=0; tick();
        if (!capture_error || occupied !== 2) $fatal(1,"zero count");
        @(negedge clk); capture_count=33; tick();
        if (!capture_error || occupied !== 2) $fatal(1,"count capacity");
        @(negedge clk); clear=1; tick();
        if (occupied !== 0 || capture_error || read_slots_valid !== 0) $fatal(1,"clear priority");
        $display("tb_imc_parallel_result_banks PASS"); $finish;
    end
endmodule
