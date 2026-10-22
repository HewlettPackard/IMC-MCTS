// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_shift_accumulator;
    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic clear = 1'b0;
    logic cmd_valid = 1'b0;
    logic [2:0] cmd_addr = '0, read_addr = '0;
    logic [7:0] adc_code = '0;
    logic [3:0] shift_amount = '0;
    logic subtract = 1'b0;
    logic signed [31:0] read_data;
    logic cmd_done, cmd_error;
    integer i;
    imc_shift_accumulator #(.ENTRIES(5)) dut (.*);
    always #5 clk = ~clk;
    task automatic tick; @(posedge clk); #1; endtask
    task automatic put(input logic [2:0] address, input logic [7:0] code,
                       input logic [3:0] shift, input logic negative);
        @(negedge clk);
        cmd_valid = 1'b1;
        cmd_addr = address;
        read_addr = address;
        adc_code = code;
        shift_amount = shift;
        subtract = negative;
        tick;
        if (cmd_done !== 1'b1) $fatal(1, "command completion missing");
    endtask
    initial begin
        tick; tick; rst_n = 1'b1;
        put(3'd4, 8'd15, 4'd4, 1'b0);
        if (read_data !== 32'sd240 || cmd_error) $fatal(1, "positive slice");
        put(3'd4, 8'd2, 4'd7, 1'b1);
        if (read_data !== -32'sd16 || cmd_error) $fatal(1, "negative slice");
        put(3'd4, 8'd1, 4'd12, 1'b0);
        if (read_data !== -32'sd16 || !cmd_error) $fatal(1, "invalid shift mutated state");
        put(3'd7, 8'd1, 4'd0, 1'b0);
        if (read_data !== 32'sd0 || !cmd_error) $fatal(1, "invalid index");
        @(negedge clk); clear = 1'b1; cmd_addr = 3'd4; read_addr = 3'd4;
        tick;
        if (read_data !== 32'sd0 || cmd_done || cmd_error) $fatal(1, "clear priority");
        @(negedge clk); clear = 1'b0; cmd_valid = 1'b0;
        for (i = 0; i < 4112; i = i + 1)
            put(3'd0, 8'd255, 4'd11, 1'b0);
        if (read_data !== 32'sd2147450880 || cmd_error) $fatal(1, "large accumulator");
        put(3'd0, 8'd255, 4'd11, 1'b0);
        if (read_data !== 32'sd2147450880 || !cmd_error) $fatal(1, "overflow must preserve sum");
        @(negedge clk); clear = 1'b1;
        tick;
        @(negedge clk); clear = 1'b0; cmd_valid = 1'b0;
        for (i = 0; i < 4112; i = i + 1)
            put(3'd0, 8'd255, 4'd11, 1'b1);
        if (read_data !== -32'sd2147450880 || cmd_error) $fatal(1, "large negative accumulator");
        put(3'd0, 8'd255, 4'd11, 1'b1);
        if (read_data !== -32'sd2147450880 || !cmd_error) $fatal(1, "negative overflow must preserve sum");
        @(negedge clk); cmd_valid = 1'b0;
        tick;
        if (cmd_done || cmd_error) $fatal(1, "completion/error must pulse");
        rst_n = 1'b0; #1;
        if (read_data !== 32'sd0) $fatal(1, "reset failed");
        $display("tb_imc_shift_accumulator PASS"); $finish;
    end
endmodule
