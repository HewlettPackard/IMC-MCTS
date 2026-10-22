// SPDX-License-Identifier: MIT
// Eight independent 12-word accumulator banks hold the 96 partial sums.
// Slot j maps to bank j%8, local word j/8. No shared write-port arbitration.
// Arithmetic and bank overhead are separate synthesis hierarchy children.
// PPA role: eight_banked_accumulators_inclusive_once
`default_nettype none
module imc_parallel_accumulators #(
    parameter int LANES = 8,
    parameter int WORDS = 12,
    parameter int ADC_BITS = 12,
    parameter int ADDR_BITS = (WORDS > 1) ? $clog2(WORDS) : 1
) (
    input  logic                      clk,
    input  logic                      rst_n,
    input  logic                      clear,
    input  logic [LANES-1:0]          cmd_valid,
    input  logic [LANES*ADDR_BITS-1:0] cmd_addr,
    input  logic [LANES*ADC_BITS-1:0]  adc_code,
    input  logic [LANES*4-1:0]         shift_amount,
    input  logic [LANES-1:0]          subtract,
    input  logic [LANES*ADDR_BITS-1:0] read_addr,
    output logic [LANES*32-1:0]        read_data,
    output logic [LANES-1:0]          cmd_done,
    output logic [LANES-1:0]          cmd_error
);
    genvar lane;
    generate
        for (lane = 0; lane < LANES; lane = lane + 1) begin
            imc_accumulator_bank #(.ENTRIES(WORDS),.ADC_BITS(ADC_BITS),.ADDR_BITS(ADDR_BITS)) u_bank (
                .clk(clk),
                .rst_n(rst_n),
                .clear(clear),
                .cmd_valid(cmd_valid[lane]),
                .cmd_addr(cmd_addr[lane*ADDR_BITS +: ADDR_BITS]),
                .adc_code(adc_code[lane*ADC_BITS +: ADC_BITS]),
                .shift_amount(shift_amount[lane*4 +: 4]),
                .subtract(subtract[lane]),
                .read_addr(read_addr[lane*ADDR_BITS +: ADDR_BITS]),
                .read_data(read_data[lane*32 +: 32]),
                .cmd_done(cmd_done[lane]),
                .cmd_error(cmd_error[lane])
            );
        end
    endgenerate
endmodule
`default_nettype wire
