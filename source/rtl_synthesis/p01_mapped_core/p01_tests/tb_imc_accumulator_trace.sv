// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_accumulator_trace #(parameter int COMMANDS = 1);
    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic clear = 1'b0, cmd_valid = 1'b0, subtract = 1'b0;
    logic [4:0] cmd_addr = '0, read_addr = '0;
    logic [7:0] adc_code = '0;
    logic [3:0] shift_amount = '0;
    logic signed [31:0] read_data;
    logic cmd_done, cmd_error;
    logic [51:0] vectors [COMMANDS];
    string vector_file, vcd_file;
    integer i;
    imc_shift_accumulator dut (.*);
    always #5 clk = ~clk;
    task automatic tick; @(posedge clk); #1; endtask
    initial begin
        if (!$value$plusargs("ACCUMULATOR_VECTORS=%s", vector_file)) $fatal(1, "vector file required");
        if ($value$plusargs("VCD=%s", vcd_file)) begin
            $dumpfile(vcd_file); $dumpvars(0, tb_imc_accumulator_trace);
        end
        $readmemh(vector_file, vectors);
        tick; tick; rst_n = 1'b1;
        for (i = 0; i < COMMANDS; i = i + 1) begin
            @(negedge clk);
            clear = (vectors[i][51:50] == 2'd0);
            cmd_valid = (vectors[i][51:50] == 2'd1);
            cmd_addr = vectors[i][49:45]; read_addr = vectors[i][49:45];
            adc_code = vectors[i][44:37]; shift_amount = vectors[i][36:33]; subtract = vectors[i][32];
            tick;
            if (cmd_error || cmd_done !== cmd_valid) $fatal(1, "trace command %0d rejected", i);
            if (vectors[i][51:50] == 2'd2 && read_data !== vectors[i][31:0])
                $fatal(1, "trace %0d got=%h expected=%h", i, read_data, vectors[i][31:0]);
        end
        $display("tb_imc_accumulator_trace PASS (%0d commands)", COMMANDS); $finish;
    end
endmodule
