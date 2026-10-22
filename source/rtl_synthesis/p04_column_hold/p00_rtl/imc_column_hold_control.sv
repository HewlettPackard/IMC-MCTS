// Track one captured column bank until its last ordered ADC input sample.
// Analog storage is external. Capture is accepted only while empty.
// Samples must match the owner and consume consecutive, in-range columns.
// Clear discards ownership; the analog responder must share reset and clear.
// PPA role: column_capture_and_ownership_control
// SPDX-License-Identifier: MIT
`default_nettype none
module imc_column_hold_control #(
    parameter int COLUMNS = 128,
    parameter int ARRAYS = 4,
    parameter int COUNT_W = $clog2(COLUMNS + 1)
) (
    input  logic                   clk,
    input  logic                   rst_n,
    input  logic                   clear,
    input  logic                   capture_req,
    input  logic [3:0]             capture_array,
    input  logic [COUNT_W-1:0]     capture_columns,
    output logic                   capture_ready,
    output logic                   analog_capture_valid,
    input  logic                   analog_capture_ready,
    input  logic                   sample_valid,
    input  logic [3:0]             sample_array,
    input  logic [COUNT_W-1:0]     sample_first,
    input  logic [1:0]             sample_count,
    output logic                   holding,
    output logic                   protocol_error
);
    typedef enum logic { ST_EMPTY, ST_HELD } state_e;
    state_e state_q, state_d;
    logic [3:0] owner_q, owner_d;
    logic [COUNT_W-1:0] columns_q, columns_d, next_q, next_d;
    logic invalid_capture, invalid_sample;

    assign holding = (state_q == ST_HELD);
    assign invalid_capture = (capture_columns == '0 || int'(capture_columns) > COLUMNS || int'(capture_array) >= ARRAYS);
    assign invalid_sample = (!holding || sample_array != owner_q || sample_first != next_q ||
        sample_count == '0 || COUNT_W'(sample_count) > columns_q - next_q);
    assign analog_capture_valid = capture_req && !holding && !invalid_capture && !clear;
    assign capture_ready = analog_capture_ready && !holding && !invalid_capture && !clear;
    assign protocol_error = !clear && ((capture_req && (holding || invalid_capture)) || (sample_valid && invalid_sample));

    always_comb begin
        state_d = state_q;
        owner_d = owner_q;
        columns_d = columns_q;
        next_d = next_q;
        if (clear) begin
            state_d = ST_EMPTY;
            owner_d = '0;
            columns_d = '0;
            next_d = '0;
        end else if (!protocol_error) begin
            unique case (state_q)
                ST_EMPTY: begin
                    if (capture_req && capture_ready) begin
                        state_d = ST_HELD;
                        owner_d = capture_array;
                        columns_d = capture_columns;
                        next_d = '0;
                    end
                end
                ST_HELD: begin
                    if (sample_valid) begin
                        next_d = next_q + COUNT_W'(sample_count);
                        if (next_d == columns_q) state_d = ST_EMPTY;
                    end
                end
                default: state_d = ST_EMPTY;
            endcase
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q <= ST_EMPTY;
            owner_q <= '0;
            columns_q <= '0;
            next_q <= '0;
        end else begin
            state_q <= state_d;
            owner_q <= owner_d;
            columns_q <= columns_d;
            next_q <= next_d;
        end
    end
endmodule
`default_nettype wire
