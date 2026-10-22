// Convert mapped value sums between packed binary64 and exact unsigned Q17.
// Values must be nonnegative multiples of 2^-17 fitting 49 bits.
// A 32-bit visit counter times a [0,1] Q17 value fits this representation.
// PPA role: mapped_statistics_value_encoding
// SPDX-License-Identifier: MIT
`default_nettype none
module imc_q17_codec (
    input  logic [63:0] binary_value,
    output logic [48:0] decoded_value,
    output logic        decode_error,
    input  logic [48:0] encoded_value,
    output logic [63:0] binary_result
);
    logic [52:0] significand, decoded_wide;
    logic [51:0] aligned;
    logic [5:0] shift_count, leading;
    logic [10:0] exponent;
    integer i;

    always_comb begin
        significand = {1'b1, binary_value[51:0]};
        shift_count = 6'(11'd1058 - binary_value[62:52]);
        decoded_wide = significand >> shift_count;
        decoded_value = decoded_wide[48:0];
        decode_error = binary_value[63] || binary_value[62:52] < 11'd1006 ||
            binary_value[62:52] > 11'd1054 || decoded_wide[52:49] != '0 ||
            (decoded_wide << shift_count) != significand;
        if (binary_value == '0) begin
            decoded_value = '0;
            decode_error = 1'b0;
        end
        leading = '0;
        for (i = 0; i < 49; i = i + 1)
            if (encoded_value[i]) leading = 6'(i);
        aligned = {3'd0, encoded_value} << (6'd52 - leading);
        exponent = 11'd1006 + {5'd0, leading};
        binary_result = {1'b0, exponent, aligned[51:0]};
        if (encoded_value == '0) binary_result = '0;
    end
endmodule
`default_nettype wire
