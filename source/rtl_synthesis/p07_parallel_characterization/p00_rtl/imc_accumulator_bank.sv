// SPDX-License-Identifier: MIT
// Twelve 32-bit partial sums with one independently costed shift/add lane.
// Reset/clear initializes all words. Invalid addresses and arithmetic errors
// leave storage unchanged. Reads are combinational; commands take one edge.
// PPA role: accumulator_registers_mux_control_and_one_arithmetic_child
`default_nettype none
module imc_accumulator_bank #(
    parameter int ENTRIES = 12,
    parameter int ADC_BITS = 12,
    parameter int ADDR_BITS = (ENTRIES > 1) ? $clog2(ENTRIES) : 1
) (
    input  logic                   clk,
    input  logic                   rst_n,
    input  logic                   clear,
    input  logic                   cmd_valid,
    input  logic [ADDR_BITS-1:0]   cmd_addr,
    input  logic [ADC_BITS-1:0]    adc_code,
    input  logic [3:0]             shift_amount,
    input  logic                   subtract,
    input  logic [ADDR_BITS-1:0]   read_addr,
    output logic signed [31:0]     read_data,
    output logic                   cmd_done,
    output logic                   cmd_error
);
    logic signed [31:0] sum_q [ENTRIES], sum_d [ENTRIES];
    logic signed [31:0] selected_sum, updated_sum;
    logic arithmetic_error, error_d;
    integer i, j;
    assign selected_sum = int'(cmd_addr) < ENTRIES ? sum_q[cmd_addr] : 32'sd0;
    imc_shift_add_lane #(.ADC_BITS(ADC_BITS)) u_arithmetic (
        .sum(selected_sum),
        .adc_code(adc_code),
        .shift_amount(shift_amount),
        .subtract(subtract),
        .updated_sum(updated_sum),
        .error(arithmetic_error)
    );
    always_comb begin
        for (j = 0; j < ENTRIES; j = j + 1) sum_d[j] = sum_q[j];
        read_data = int'(read_addr) < ENTRIES ? sum_q[read_addr] : 32'sd0;
        error_d = 1'b0;
        if (clear) begin
            for (j = 0; j < ENTRIES; j = j + 1) sum_d[j] = '0;
        end else if (cmd_valid) begin
            if (int'(cmd_addr) >= ENTRIES || arithmetic_error) error_d = 1'b1;
            else sum_d[cmd_addr] = updated_sum;
        end
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < ENTRIES; i = i + 1) sum_q[i] <= '0;
            cmd_done <= 1'b0;
            cmd_error <= 1'b0;
        end else begin
            for (i = 0; i < ENTRIES; i = i + 1) sum_q[i] <= sum_d[i];
            cmd_done <= cmd_valid && !clear;
            cmd_error <= error_d;
        end
    end
endmodule
`default_nettype wire
