// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_parallel_accumulators;
    logic clk=0, rst_n=0, clear=0;
    logic [7:0] cmd_valid=0, subtract=0, cmd_done, cmd_error;
    logic [31:0] cmd_addr=0, shift_amount=0, read_addr=0;
    logic [95:0] adc_code=0;
    logic [255:0] read_data;
    integer i;
    imc_parallel_accumulators dut (.*);
    always #5 clk=~clk;
    task automatic tick; @(posedge clk); #1; endtask
    initial begin
        tick(); tick(); @(negedge clk); rst_n=1;
        cmd_valid='1;
        for (i=0;i<8;i=i+1) adc_code[i*12 +: 12]=12'(4095-i);
        tick();
        if (cmd_done !== 8'hff || cmd_error !== 0) $fatal(1,"parallel command");
        for (i=0;i<8;i=i+1)
            if (read_data[i*32 +: 32] !== 32'(4095-i)) $fatal(1,"lane collision");
        @(negedge clk); cmd_addr={8{4'd11}}; read_addr=cmd_addr;
        shift_amount={8{4'd7}}; subtract='1; tick();
        for (i=0;i<8;i=i+1)
            if ($signed(read_data[i*32 +: 32]) !== -32'((4095-i)*128)) $fatal(1,"last word/12-bit subtract");
        @(negedge clk); cmd_addr={8{4'd15}}; tick();
        if (cmd_error !== 8'hff) $fatal(1,"non-power-of-two index");
        for (i=0;i<8;i=i+1)
            if ($signed(read_data[i*32 +: 32]) !== -32'((4095-i)*128)) $fatal(1,"invalid write modified bank");
        @(negedge clk); cmd_addr={8{4'd11}}; shift_amount={8{4'd12}}; tick();
        if (cmd_error !== 8'hff) $fatal(1,"invalid shift");
        @(negedge clk); clear=1; tick();
        if (read_data !== 0 || cmd_done !== 0 || cmd_error !== 0) $fatal(1,"clear priority");
        @(negedge clk); clear=0; cmd_valid=0; read_addr=0; #1;
        for (i=0;i<8;i=i+1) if (read_data[i*32 +: 32] !== 0) $fatal(1,"clear all words");
        $display("tb_imc_parallel_accumulators PASS"); $finish;
    end
endmodule
