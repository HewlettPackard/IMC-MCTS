// SPDX-License-Identifier: MIT
// One signed shift/add lane updates a finite bank of 32-bit partial sums.
// Clear has priority. Invalid index, shift, or overflow leaves storage intact.
// Commands complete in one edge; reads are combinational and nondestructive.
// PPA role: neural_shift_add_and_accumulator_registers
`default_nettype none
module imc_shift_accumulator #(
    parameter int ENTRIES = 32,
    parameter int ADDR_W = (ENTRIES > 1) ? $clog2(ENTRIES) : 1
) (
    input  logic                     clk,
    input  logic                     rst_n,
    input  logic                     clear,
    input  logic                     cmd_valid,
    input  logic [ADDR_W-1:0]        cmd_addr,
    input  logic [7:0]                adc_code,
    input  logic [3:0]                shift_amount,
    input  logic                     subtract,
    input  logic [ADDR_W-1:0]        read_addr,
    output logic signed [31:0]        read_data,
    output logic                     cmd_done,
    output logic                     cmd_error
);
    localparam int ACC_W = 32;
    logic signed [ACC_W-1:0] sum_q [ENTRIES];
    logic signed [ACC_W-1:0] sum_d [ENTRIES];
    logic signed [ACC_W:0] term;
    logic signed [ACC_W:0] updated;
    logic error_d;
    integer i, j;

    always_comb begin
        for (j = 0; j < ENTRIES; j = j + 1)
            sum_d[j] = sum_q[j];
        read_data = '0;
        term = $signed({{(ACC_W-7){1'b0}}, adc_code}) <<< shift_amount;
        updated = '0;
        error_d = 1'b0;
        if (int'(read_addr) < ENTRIES)
            read_data = sum_q[read_addr];
        if (clear) begin
            for (j = 0; j < ENTRIES; j = j + 1)
                sum_d[j] = '0;
        end else if (cmd_valid) begin
            if (int'(cmd_addr) >= ENTRIES || shift_amount > 4'd11) begin
                error_d = 1'b1;
            end else begin
                updated = $signed({sum_q[cmd_addr][ACC_W-1], sum_q[cmd_addr]});
                if (subtract)
                    updated = updated - term;
                else
                    updated = updated + term;
                if (updated[ACC_W] != updated[ACC_W-1])
                    error_d = 1'b1;
                else
                    sum_d[cmd_addr] = updated[ACC_W-1:0];
            end
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < ENTRIES; i = i + 1)
                sum_q[i] <= '0;
            cmd_done <= 1'b0;
            cmd_error <= 1'b0;
        end else begin
            for (i = 0; i < ENTRIES; i = i + 1)
                sum_q[i] <= sum_d[i];
            cmd_done <= cmd_valid && !clear;
            cmd_error <= error_d;
        end
    end
endmodule
`default_nettype wire
