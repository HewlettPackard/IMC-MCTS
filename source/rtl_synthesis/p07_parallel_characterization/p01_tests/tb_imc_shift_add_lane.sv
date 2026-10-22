// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_shift_add_lane;
    logic signed [31:0] sum=0, updated_sum;
    logic [11:0] adc_code=0;
    logic [3:0] shift_amount=0;
    logic subtract=0, error;
    imc_shift_add_lane dut (.*);
    initial begin
        sum=32'sd100; adc_code=12'd4095; shift_amount=4'd7; #1;
        if (error || updated_sum !== 32'sd524260) $fatal(1,"12-bit add");
        subtract=1; #1;
        if (error || updated_sum !== -32'sd524060) $fatal(1,"signed subtract");
        sum=32'sh7fffffff; subtract=0; shift_amount=0; adc_code=1; #1;
        if (!error || updated_sum !== sum) $fatal(1,"positive overflow");
        sum=32'sh80000000; subtract=1; #1;
        if (!error || updated_sum !== sum) $fatal(1,"negative overflow");
        sum=0; adc_code=4095; subtract=0; shift_amount=11; #1;
        if (error || updated_sum !== 32'sd8386560) $fatal(1,"maximum legal shift");
        shift_amount=12; #1;
        if (!error || updated_sum !== 0) $fatal(1,"invalid shift");
        $display("tb_imc_shift_add_lane PASS"); $finish;
    end
endmodule
