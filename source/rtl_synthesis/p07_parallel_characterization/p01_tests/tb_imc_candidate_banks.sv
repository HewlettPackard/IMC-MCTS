// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_candidate_banks;
    logic clk=0, rst_n=0, clear=0, capture_valid=0, capture_bank=0;
    logic [4:0] capture_count=0;
    logic [2047:0] capture_data=0;
    logic capture_ready, capture_error, release_valid=0, release_bank=0, read_bank=0;
    logic [3:0] read_index=0;
    logic [127:0] read_data;
    logic read_slots_valid;
    logic [1:0] occupied;
    integer i;
    imc_candidate_banks dut (.*);
    always #5 clk=~clk;
    task automatic tick; @(posedge clk); #1; endtask
    initial begin
        tick(); tick(); @(negedge clk); rst_n=1; capture_valid=1; capture_count=16;
        for (i=0;i<16;i=i+1) capture_data[i*128 +: 128]=128'(i+100);
        tick(); @(negedge clk); capture_valid=0;
        for (i=0;i<16;i=i+1) begin
            read_index=4'(i); #1;
            if (!read_slots_valid || read_data !== 128'(i+100)) $fatal(1,"operand index/order");
        end
        capture_valid=1; release_valid=1; release_bank=0; capture_data='1; tick();
        if (!capture_error || occupied !== 0) $fatal(1,"same-edge reuse should wait");
        @(negedge clk); release_valid=0; capture_count=3; tick();
        @(negedge clk); capture_valid=0; read_index=3; #1;
        if (read_slots_valid || read_data !== 0) $fatal(1,"partial batch padding");
        clear=1; tick();
        if (occupied !== 0 || capture_error) $fatal(1,"clear");
        $display("tb_imc_candidate_banks PASS"); $finish;
    end
endmodule
