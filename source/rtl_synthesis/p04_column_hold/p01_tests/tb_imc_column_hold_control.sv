// Directed ownership, backpressure, invalid-transfer and reset checks.
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_column_hold_control;
    logic clk = 1'b0, rst_n = 1'b0, clear = 1'b0;
    logic capture_req = 1'b0, capture_ready, analog_capture_valid;
    logic analog_capture_ready = 1'b0;
    logic [3:0] capture_array = '0;
    logic [3:0] capture_columns = 4'd8;
    logic sample_valid = 1'b0;
    logic [3:0] sample_array = '0, sample_first = '0;
    logic [1:0] sample_count = '0;
    logic holding, protocol_error;
`ifdef IMC_POST_SYNTH
    imc_column_hold_control dut (.*);
`else
    imc_column_hold_control #(.COLUMNS(8), .ARRAYS(2)) dut (.*);
`endif
    always #5 clk = ~clk;
    task automatic tick; @(posedge clk); #1; endtask

    task automatic sample(input logic [3:0] owner, first, input logic [1:0] count, input logic bad);
        @(negedge clk); sample_valid = 1'b1; sample_array = owner; sample_first = first; sample_count = count;
        #1; if (protocol_error !== bad) $fatal(1, "sample error indication");
        tick;
        @(negedge clk); sample_valid = 1'b0;
    endtask

    initial begin
        tick; tick; rst_n = 1'b1;
        @(negedge clk); capture_req = 1'b1;
        repeat (3) begin
            tick;
            if (holding || capture_ready || !analog_capture_valid || protocol_error) $fatal(1, "capture stall");
        end
        @(negedge clk); analog_capture_ready = 1'b1;
        tick;
        if (!holding || capture_ready || analog_capture_valid) $fatal(1, "capture ownership");
        @(negedge clk); capture_req = 1'b0;
        sample(4'd1, 4'd0, 2'd3, 1'b1);
        sample(4'd0, 4'd1, 2'd3, 1'b1);
        sample(4'd0, 4'd0, 2'd0, 1'b1);
        sample(4'd0, 4'd0, 2'd3, 1'b0);
        @(negedge clk); capture_req = 1'b1;
        #1; if (!protocol_error || capture_ready || analog_capture_valid) $fatal(1, "overwrite accepted");
        tick;
        @(negedge clk); capture_req = 1'b0;
        sample(4'd0, 4'd3, 2'd3, 1'b0);
        sample(4'd0, 4'd6, 2'd3, 1'b1);
        sample(4'd0, 4'd6, 2'd2, 1'b0);
        if (holding) $fatal(1, "last sample did not release");
        sample(4'd0, 4'd0, 2'd1, 1'b1);
        @(negedge clk); capture_req = 1'b1; capture_columns = 4'd9;
        #1; if (!protocol_error || analog_capture_valid) $fatal(1, "capacity accepted");
        tick;
        @(negedge clk); capture_columns = 4'd0;
        #1; if (!protocol_error || analog_capture_valid) $fatal(1, "empty capture accepted");
        tick;
        @(negedge clk); capture_columns = 4'd1; capture_array = 4'd2;
        #1; if (!protocol_error || analog_capture_valid) $fatal(1, "invalid owner accepted");
        tick;
        @(negedge clk); capture_array = 4'd1;
        tick;
        @(negedge clk); capture_req = 1'b0; clear = 1'b1;
        tick;
        if (holding || analog_capture_valid || capture_ready || protocol_error) $fatal(1, "clear");
        @(negedge clk); clear = 1'b0; capture_req = 1'b1;
        tick;
        @(negedge clk); capture_req = 1'b0;
        sample(4'd1, 4'd0, 2'd1, 1'b0);
        if (holding) $fatal(1, "reuse");
        @(negedge clk); capture_req = 1'b1;
        tick;
        @(negedge clk); capture_req = 1'b0; rst_n = 1'b0;
        tick; tick;
        if (holding) $fatal(1, "reset");
        $display("tb_imc_column_hold_control PASS"); $finish;
    end
endmodule
