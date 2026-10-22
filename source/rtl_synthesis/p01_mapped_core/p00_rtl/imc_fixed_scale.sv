// SPDX-License-Identifier: MIT
// Signed 32-bit power-of-two scaling, nearest-even rounding and saturation.
// Positive shift divides; negative shift multiplies. Zero never saturates.
// PPA role: neural_shared_scale_and_saturation
`default_nettype none
module imc_fixed_scale (
    input  logic signed [31:0] value,
    input  logic signed [7:0]  shift,
    output logic signed [31:0] scaled,
    output logic              saturated
);
    logic [63:0] magnitude, rounded, residue, half;
    logic [7:0] amount;

    always_comb begin
        magnitude = value[31] ? $unsigned(-$signed({{32{value[31]}}, value})) : {32'd0, value};
        rounded = magnitude;
        residue = '0;
        half = '0;
        amount = $unsigned(shift);
        scaled = '0;
        saturated = 1'b0;
        if (shift[7]) begin
            amount = 8'(-$signed({shift[7], shift}));
            if (amount >= 8'd32)
                rounded = (magnitude == '0) ? 64'd0 : 64'hffffffffffffffff;
            else
                rounded = magnitude << amount;
        end else if (amount != '0) begin
            if (amount >= 8'd33) begin
                rounded = '0;
            end else begin
                rounded = magnitude >> amount;
                residue = magnitude & ((64'd1 << amount) - 64'd1);
                half = 64'd1 << (amount - 8'd1);
                if (residue > half || (residue == half && rounded[0]))
                    rounded = rounded + 64'd1;
            end
        end
        if (value[31]) begin
            if (rounded > 64'h0000000080000000) begin
                scaled = 32'sh80000000;
                saturated = 1'b1;
            end else begin
                scaled = -$signed(rounded[31:0]);
            end
        end else begin
            if (rounded > 64'h000000007fffffff) begin
                scaled = 32'sh7fffffff;
                saturated = 1'b1;
            end else begin
                scaled = $signed(rounded[31:0]);
            end
        end
    end
endmodule
`default_nettype wire
