// Exercise exact mapped-statistics encoding with independent binary64 vectors.
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_q17_codec;
    logic [63:0] binary_value, binary_result;
    logic [48:0] decoded_value, encoded_value;
    logic decode_error;
    logic [255:0] vectors [0:1023];
    integer count, i;
    string path;
    imc_q17_codec dut (.*);
    initial begin
        if (!$value$plusargs("VECTORS=%s",path)) $fatal(1,"VECTORS missing");
        if (!$value$plusargs("COUNT=%d",count)) $fatal(1,"COUNT missing");
        $readmemh(path,vectors,0,count-1);
        for (i=0;i<count;i=i+1) begin
            binary_value=vectors[i][255:192]; encoded_value=vectors[i][191:143]; #1;
            if (decode_error !== vectors[i][93] || binary_result !== vectors[i][63:0]) $fatal(1,"codec error at %0d",i);
            if (!decode_error && decoded_value !== vectors[i][142:94]) $fatal(1,"decoded sum differs at %0d",i);
        end
        $display("tb_imc_q17_codec PASS %0d vectors",count); $finish;
    end
endmodule
