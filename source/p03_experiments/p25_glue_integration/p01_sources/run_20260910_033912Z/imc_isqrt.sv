// Floor square root of a 104-bit unsigned radicand, two input bits per cycle.
// PPA role: UCB_integer_square_root
// SPDX-License-Identifier: MIT
`default_nettype none
module imc_isqrt (
    input logic clk,
    input logic rst_n,
    input logic clear,
    input logic start,
    input logic [103:0] radicand,
    output logic ready,
    output logic done,
    output logic [51:0] root
);
    typedef enum logic { ST_IDLE, ST_BITS } state_e;
    state_e state_q, state_d;
    logic [103:0] radicand_q, radicand_d;
    logic [105:0] remainder_q, remainder_d, trial;
    logic [51:0] root_d;
    logic [5:0] count_q, count_d;
    logic done_d;
    assign ready = rst_n && state_q == ST_IDLE && !clear;

    always_comb begin
        state_d = state_q;
        radicand_d = radicand_q;
        remainder_d = remainder_q;
        root_d = root;
        count_d = count_q;
        done_d = 1'b0;
        trial = {52'd0, root, 2'b01};
        if (clear) begin
            state_d = ST_IDLE;
            radicand_d = '0;
            remainder_d = '0;
            root_d = '0;
            count_d = '0;
        end else begin
            unique case (state_q)
                ST_IDLE: if (start) begin
                    radicand_d = radicand;
                    remainder_d = '0;
                    root_d = '0;
                    count_d = 6'd52;
                    state_d = ST_BITS;
                end
                ST_BITS: begin
                    remainder_d = (remainder_q << 2) | {104'd0, radicand_q[103:102]};
                    radicand_d = radicand_q << 2;
                    root_d = root << 1;
                    if (remainder_d >= trial) begin
                        remainder_d = remainder_d - trial;
                        root_d[0] = 1'b1;
                    end
                    count_d = count_q - 6'd1;
                    if (count_q == 6'd1) begin
                        state_d = ST_IDLE;
                        done_d = 1'b1;
                    end
                end
                default: state_d = ST_IDLE;
            endcase
        end
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q <= ST_IDLE;
            radicand_q <= '0;
            remainder_q <= '0;
            root <= '0;
            count_q <= '0;
            done <= 1'b0;
        end else begin
            state_q <= state_d;
            radicand_q <= radicand_d;
            remainder_q <= remainder_d;
            root <= root_d;
            count_q <= count_d;
            done <= done_d;
        end
    end
endmodule
`default_nettype wire
