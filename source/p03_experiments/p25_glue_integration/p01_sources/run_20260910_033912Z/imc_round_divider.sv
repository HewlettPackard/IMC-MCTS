// SPDX-License-Identifier: MIT
// Unsigned 48/32 restoring division with nearest-even quotient rounding.
// One setup edge, NUM_W bit edges, then one rounding edge; busy ignores start.
// Clear aborts. A zero denominator completes with error and zero outputs.
// PPA role: neural_probability_divider_and_rounding
`default_nettype none
module imc_round_divider #(
    parameter int NUM_W = 48,
    parameter int DEN_W = 32
) (
    input  logic                 clk,
    input  logic                 rst_n,
    input  logic                 clear,
    input  logic                 start,
    input  logic [NUM_W-1:0]      numerator,
    input  logic [DEN_W-1:0]      denominator,
    output logic                 ready,
    output logic                 done,
    output logic                 error,
    output logic [NUM_W-1:0]      quotient,
    output logic [DEN_W-1:0]      remainder
);
    localparam int COUNT_W = $clog2(NUM_W + 1);
    typedef enum logic [1:0] { ST_IDLE, ST_BITS, ST_ROUND } state_e;
    state_e state_q, state_d;
    logic [NUM_W-1:0] numerator_q, numerator_d;
    logic [DEN_W-1:0] denominator_q, denominator_d;
    logic [NUM_W-1:0] quotient_d;
    logic [DEN_W-1:0] remainder_d;
    logic [COUNT_W-1:0] count_q, count_d;
    logic [DEN_W:0] trial, doubled;
    logic done_d, error_d;

    assign ready = (state_q == ST_IDLE) && !clear;

    always_comb begin
        state_d = state_q;
        numerator_d = numerator_q;
        denominator_d = denominator_q;
        quotient_d = quotient;
        remainder_d = remainder;
        count_d = count_q;
        trial = {remainder, numerator_q[NUM_W-1]};
        doubled = {remainder, 1'b0};
        done_d = 1'b0;
        error_d = 1'b0;
        if (clear) begin
            state_d = ST_IDLE;
            numerator_d = '0;
            denominator_d = '0;
            quotient_d = '0;
            remainder_d = '0;
            count_d = '0;
        end else begin
            unique case (state_q)
                ST_IDLE: begin
                    if (start) begin
                        numerator_d = numerator;
                        denominator_d = denominator;
                        quotient_d = '0;
                        remainder_d = '0;
                        count_d = COUNT_W'(NUM_W);
                        if (denominator == '0) begin
                            done_d = 1'b1;
                            error_d = 1'b1;
                        end else begin
                            state_d = ST_BITS;
                        end
                    end
                end
                ST_BITS: begin
                    numerator_d = {numerator_q[NUM_W-2:0], 1'b0};
                    quotient_d = {quotient[NUM_W-2:0], 1'b0};
                    if (trial >= {1'b0, denominator_q}) begin
                        trial = trial - {1'b0, denominator_q};
                        quotient_d[0] = 1'b1;
                    end
                    remainder_d = trial[DEN_W-1:0];
                    count_d = count_q - COUNT_W'(1);
                    if (count_q == COUNT_W'(1))
                        state_d = ST_ROUND;
                end
                ST_ROUND: begin
                    if (doubled > {1'b0, denominator_q} ||
                        (doubled == {1'b0, denominator_q} && quotient[0]))
                        quotient_d = quotient + NUM_W'(1);
                    done_d = 1'b1;
                    state_d = ST_IDLE;
                end
                default: begin
                    state_d = ST_IDLE;
                    error_d = 1'b1;
                end
            endcase
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q <= ST_IDLE;
            numerator_q <= '0;
            denominator_q <= '0;
            quotient <= '0;
            remainder <= '0;
            count_q <= '0;
            done <= 1'b0;
            error <= 1'b0;
        end else begin
            state_q <= state_d;
            numerator_q <= numerator_d;
            denominator_q <= denominator_d;
            quotient <= quotient_d;
            remainder <= remainder_d;
            count_q <= count_d;
            done <= done_d;
            error <= error_d;
        end
    end
endmodule
`default_nettype wire
