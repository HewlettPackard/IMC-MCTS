// Exact remainder, bounded denominators, busy behavior and interrupted division.
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_choice_remainder;
    logic clk = '0;
    logic rst_n = '0;
    logic clear = '0;
    logic start = '0;
    logic [31:0] numerator = '0;
    logic [6:0] denominator = '0;
    logic ready, done, error;
    logic [31:0] quotient;
    logic [6:0] remainder;
    integer divisor, sample, elapsed;
    logic [31:0] value, expected;

    imc_round_divider #(.NUM_W(32), .DEN_W(7)) dut (.*);
    always #5 clk = ~clk;

    task automatic tick;
        @(posedge clk); #1;
    endtask
    task automatic run_choice(input logic [31:0] word_value, input logic [6:0] count);
        @(negedge clk); numerator=word_value; denominator=count; start=1;
        if (!ready) $fatal(1,"not ready before choice");
        tick();
        @(negedge clk); start=0; numerator='1; denominator='0;
        elapsed=0;
        while (!done) begin
            tick(); elapsed=elapsed+1;
        end
        if (count == 0) begin
            if (!error || remainder != 0) $fatal(1,"zero divisor did not fail");
        end else begin
            expected=word_value % 32'(count);
            if (error || remainder !== 7'(expected) || elapsed != 33)
                $fatal(1,"choice word=%h count=%0d remainder=%0d expected=%0d cycles=%0d",
                    word_value,count,remainder,expected,elapsed);
        end
        tick();
        if (done || !ready) $fatal(1,"completion pulse or ready differs");
    endtask

    initial begin
        tick(); tick(); @(negedge clk); rst_n=1;
        for (divisor=1; divisor<=81; divisor=divisor+1) begin
            for (sample=0; sample<8; sample=sample+1) begin
                case (sample)
                    0: value=0;
                    1: value=1;
                    2: value=32'(divisor-1);
                    3: value=32'(divisor);
                    4: value=32'(divisor+1);
                    5: value=32'hffffffff;
                    6: value=32'h80000000;
                    default: value=32'h9e3779b9 ^ 32'(divisor);
                endcase
                run_choice(value,7'(divisor));
            end
        end
        run_choice(32'hffffffff,0);
        @(negedge clk); start=1; numerator=32'hffffffff; denominator=81;
        tick(); @(negedge clk); start=0;
        repeat (8) tick();
        @(negedge clk); clear=1;
        tick();
        if (done || remainder != 0) $fatal(1,"clear retained pending division");
        @(negedge clk); clear=0;
        run_choice(32'hffffffff,81);
        @(negedge clk); start=1; numerator=32'h80000000; denominator=80;
        tick(); @(negedge clk); start=0;
        repeat (8) tick();
        @(negedge clk); rst_n=0;
        tick(); tick(); @(negedge clk); rst_n=1;
        run_choice(32'h80000000,80);
        $display("tb_imc_choice_remainder PASS 648 choices, zero divisor, clear, reset");
        $finish;
    end
endmodule
