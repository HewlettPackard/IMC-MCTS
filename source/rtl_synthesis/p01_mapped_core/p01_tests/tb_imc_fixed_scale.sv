// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_fixed_scale #(parameter int CASES = 195);
    logic signed [31:0] value;
    logic signed [7:0] shift;
    logic signed [31:0] scaled;
    logic saturated;
    logic [72:0] vectors [CASES];
    string path;
    integer i;
    imc_fixed_scale dut (.*);
    initial begin
        if (!$value$plusargs("VECTORS=%s", path)) $fatal(1, "VECTORS required");
        $readmemh(path, vectors);
        for (i = 0; i < CASES; i = i + 1) begin
            value = vectors[i][72:41]; shift = vectors[i][40:33];
            #1;
            if (scaled !== vectors[i][31:0] || saturated !== vectors[i][32])
                $fatal(1, "scale %0d value=%h shift=%0d got=%h expected=%h", i, value, shift, scaled, vectors[i][31:0]);
        end
        $display("tb_imc_fixed_scale PASS (%0d cases)", CASES); $finish;
    end
endmodule
