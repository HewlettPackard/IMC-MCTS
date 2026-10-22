// SPDX-License-Identifier: MIT
// Characterization wrapper for two banks of sixteen 128-bit UCB operands.
// Group loading is external; this block does not replace the SRAM scheduler.
// Release occurs only after the group's reduction has completed.
// PPA role: two_candidate_operand_banks_inclusive_once
`default_nettype none
module imc_candidate_banks (
    input  logic          clk,
    input  logic          rst_n,
    input  logic          clear,
    input  logic          capture_valid,
    input  logic          capture_bank,
    input  logic [4:0]    capture_count,
    input  logic [2047:0] capture_data,
    output logic          capture_ready,
    output logic          capture_error,
    input  logic          release_valid,
    input  logic          release_bank,
    input  logic          read_bank,
    input  logic [3:0]    read_index,
    output logic [127:0]  read_data,
    output logic          read_slots_valid,
    output logic [1:0]    occupied
);
    imc_parallel_result_banks #(.WORD_BITS(128),.WORDS(16),.BUS_BITS(128)) u_operands (
        .clk(clk),
        .rst_n(rst_n),
        .clear(clear),
        .capture_valid(capture_valid),
        .capture_bank(capture_bank),
        .capture_count(capture_count),
        .capture_data(capture_data),
        .capture_ready(capture_ready),
        .capture_error(capture_error),
        .release_valid(release_valid),
        .release_bank(release_bank),
        .read_bank(read_bank),
        .read_index(read_index),
        .read_data(read_data),
        .read_slots_valid(read_slots_valid),
        .occupied(occupied)
    );
endmodule
`default_nettype wire
