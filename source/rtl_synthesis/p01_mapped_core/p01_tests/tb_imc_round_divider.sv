// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_round_divider #(parameter int DIVISIONS = 12);
    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic clear = 1'b0, start = 1'b0;
    logic [47:0] numerator = '0;
    logic [31:0] denominator = '0;
    logic ready, done, error;
    logic [47:0] quotient;
    logic [31:0] remainder;
    integer i, case_index;
    logic [159:0] vectors [DIVISIONS];
    string vector_file;
    imc_round_divider dut (.*);
    always #5 clk = ~clk;
    task automatic tick; @(posedge clk); #1; endtask
    task automatic divide(input logic [47:0] n, input logic [31:0] d,
                          input logic [47:0] q, input logic [31:0] r);
        @(negedge clk); start = 1'b1; numerator = n; denominator = d;
        tick;
        if (ready || done) $fatal(1, "setup service");
        @(negedge clk); start = 1'b0;
        for (i = 0; i < 48; i = i + 1) begin
            tick;
            if (done || ready) $fatal(1, "divider completed before rounding edge");
        end
        tick;
        if (!done || !ready || error || quotient !== q || remainder !== r)
            $fatal(1, "divide n=%h d=%h q=%h expected=%h r=%h expected=%h", n,d,quotient,q,remainder,r);
        tick;
        if (done || error) $fatal(1, "completion must pulse");
    endtask
    initial begin
        tick; tick; rst_n = 1'b1;
        if ($value$plusargs("DIVISION_VECTORS=%s", vector_file)) begin
            $readmemh(vector_file, vectors);
            for (case_index = 0; case_index < DIVISIONS; case_index = case_index + 1)
                divide(vectors[case_index][159:112], vectors[case_index][111:80],
                       vectors[case_index][79:32], vectors[case_index][31:0]);
        end
        divide(48'd5, 32'd2, 48'd2, 32'd1);
        divide(48'd7, 32'd2, 48'd4, 32'd1);
        divide(48'd8, 32'd3, 48'd3, 32'd2);
        divide(48'd0, 32'hffffffff, 48'd0, 32'd0);
        divide(48'hffffffffffff, 32'd1, 48'hffffffffffff, 32'd0);
        divide(48'hffffffffffff, 32'hffffffff, 48'd65536, 32'd65535);
        divide(48'h400000000000, 32'h40000000, 48'd65536, 32'd0);
        @(negedge clk); start = 1'b1; numerator = 48'd123; denominator = '0;
        tick;
        if (!done || !error || !ready || quotient !== '0 || remainder !== '0) $fatal(1, "zero denominator");
        @(negedge clk); numerator = 48'd7; denominator = 32'd2;
        tick;
        @(negedge clk); numerator = 48'd999; denominator = 32'd1;
        tick;
        @(negedge clk); start = 1'b0;
        for (i = 0; i < 47; i = i + 1) tick;
        tick;
        if (!done || quotient !== 48'd4) $fatal(1, "busy start corrupted division");
        @(negedge clk); start = 1'b1; numerator = 48'd999; denominator = 32'd7;
        tick;
        @(negedge clk); clear = 1'b1;
        tick;
        if (done || error || quotient !== '0 || remainder !== '0) $fatal(1, "clear abort");
        @(negedge clk); clear = 1'b0; start = 1'b0;
        tick;
        if (!ready) $fatal(1, "clear did not return idle");
        $display("tb_imc_round_divider PASS"); $finish;
    end
endmodule
