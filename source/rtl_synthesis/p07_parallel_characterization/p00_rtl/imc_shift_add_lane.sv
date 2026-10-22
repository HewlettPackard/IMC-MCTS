// SPDX-License-Identifier: MIT
// One 12-bit code is shifted and added to a signed 32-bit partial sum.
// Shifts above 11 or signed overflow leave the input sum unchanged.
// PPA role: bare_shift_add_lane_without_register_bank_or_read_mux
`default_nettype none
module imc_shift_add_lane #(
    parameter int ADC_BITS = 12,
    parameter int ACC_BITS = 32
) (
    input  logic signed [ACC_BITS-1:0] sum,
    input  logic [ADC_BITS-1:0]        adc_code,
    input  logic [3:0]                shift_amount,
    input  logic                      subtract,
    output logic signed [ACC_BITS-1:0] updated_sum,
    output logic                      error
);
    logic signed [ACC_BITS:0] term, wide_sum, result;
    always_comb begin
        term = $signed({{(ACC_BITS+1-ADC_BITS){1'b0}},adc_code}) <<< shift_amount;
        wide_sum = $signed({sum[ACC_BITS-1],sum});
        result = subtract ? wide_sum - term : wide_sum + term;
        error = shift_amount > 4'd11 || result[ACC_BITS] != result[ACC_BITS-1];
        updated_sum = error ? sum : result[ACC_BITS-1:0];
    end
endmodule
`default_nettype wire
