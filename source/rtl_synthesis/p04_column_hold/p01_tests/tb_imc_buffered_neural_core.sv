// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_buffered_neural_core #(
    parameter int INPUTS = 162,
    parameter int HIDDEN = 96,
    parameter int ADC_GROUPS = 1611,
    parameter int RESULT_WORDS = 31,
    parameter int STALL = 0,
    parameter int FAULT = 0,
    parameter int REPEATS = 2
);
    logic clk = 1'b0, rst_n = 1'b0;
    logic start = 1'b0, ready;
    logic [20:0] board_base = '0, neural_base = '0;
    logic [5:0] hidden_shift = '0;
    logic signed [7:0] logit_shift = '0;
    logic result_valid, result_ready = 1'b0;
    logic [31:0] value_code;
    logic [3:0] result_error;
    logic drive_valid, drive_ready = 1'b1, array_enable;
    logic [3:0] array_id;
    logic [7:0] row_start, column_start;
    logic [4:0] row_count;
    logic [15:0] row_bits;
    logic [2:0] input_bit;
    logic [1:0] column_count;
    logic mux_select, sample_hold, adc_req_valid, adc_req_ready = 1'b1;
    logic adc_rsp_valid = 1'b0, adc_rsp_ready, adc_rsp_error = 1'b0;
    logic [23:0] adc_rsp_codes = '0;
    logic hidden_saturated, logit_saturated;
    logic [5:0] debug_state;
    logic [2:0] bank_valid, bank_ready = '1, bank_write, bank_rsp_valid = '0;
    logic [50:0] bank_addr;
    logic [95:0] bank_wdata, bank_rdata = '0;
    logic [31:0] memory [393216];
    logic [31:0] expected [RESULT_WORDS];
    logic [71:0] adc_vectors [ADC_GROUPS];
    logic [23:0] pending_codes = '0;
    logic pending_error = 1'b0;
    logic immediate_result = 1'b0;
    integer adc_index = 0, adc_delay = 0;
    integer cycle = 0, run_index = -1, start_cycle, result_cycle;
    integer bank, address, i, repeat_index, events;
    integer board_address, neural_address, hidden_amount, logit_amount, expected_value;
    integer expected_error;
    string fixture, events_path, vcd_path;
`ifdef IMC_POST_SYNTH
    imc_buffered_neural_core dut (.*);
`else
    imc_buffered_neural_core #(.INPUTS(INPUTS), .HIDDEN(HIDDEN)) dut (.*);
`endif
    always #5 clk = ~clk;
    task automatic tick; @(posedge clk); #1; endtask

    localparam int HOLD_ADC_LIMIT = ADC_GROUPS;
    wire signed [31:0] hold_run = run_index;
    `include "p01_tests/held_columns.svh"
    always @(negedge clk) begin
        cycle = cycle + 1;
        bank_ready = (STALL != 0 && cycle % 7 < 2) ? 3'b000 : 3'b111;
        drive_ready = !(STALL != 0 && cycle % 5 == 0);
        adc_req_ready = !(STALL != 0 && cycle % 11 < 2);
    end

    always @(posedge clk) begin
        bank_rsp_valid <= '0;
        if (!rst_n) begin
            bank_rdata <= '0;
            adc_rsp_valid <= 1'b0;
            adc_rsp_error <= 1'b0;
            adc_rsp_codes <= '0;
            adc_delay = 0;
            adc_index = 0;
        end else begin
            if (start && ready) adc_index = 0;
            for (bank = 0; bank < 3; bank = bank + 1) begin
                if (bank_valid[bank] && bank_ready[bank]) begin
                    address = bank*131072 + int'(bank_addr[bank*17 +: 17]);
                    bank_rsp_valid[bank] <= 1'b1;
                    if (bank_write[bank]) begin
                        memory[address] <= bank_wdata[bank*32 +: 32];
                        bank_rdata[bank*32 +: 32] <= '0;
                    end else begin
                        bank_rdata[bank*32 +: 32] <= memory[address];
                    end
                    $fdisplay(events, "mem,%0d,%0d,%0d,%0d,%08h", run_index, cycle, address*4,
                        bank_write[bank], bank_write[bank] ? bank_wdata[bank*32 +: 32] : memory[address]);
                end
            end
            if (adc_rsp_valid && adc_rsp_ready) begin
                adc_rsp_valid <= 1'b0;
                adc_rsp_error <= 1'b0;
                $fdisplay(events, "adc_done,%0d,%0d", run_index, cycle);
            end
            if (adc_delay > 0) begin
                adc_delay = adc_delay - 1;
                if (adc_delay == 0) begin
                    adc_rsp_valid <= 1'b1;
                    adc_rsp_codes <= pending_codes;
                    adc_rsp_error <= pending_error;
                end
            end
            if (drive_valid && drive_ready)
                $fdisplay(events, "drive,%0d,%0d,%0d,%0d,%0d,%0d,%04h", run_index, cycle,
                    array_id, row_start, row_count, input_bit, row_bits);
            if (mux_select) $fdisplay(events, "mux,%0d,%0d", run_index, cycle);
            if (sample_hold) $fdisplay(events, "sample,%0d,%0d,%0d", run_index, cycle, column_count);
            if (hidden_saturated) $fdisplay(events, "hidden_clip,%0d,%0d", run_index, cycle);
            if (logit_saturated) $fdisplay(events, "logit_clip,%0d,%0d", run_index, cycle);
            if (adc_req_valid && adc_req_ready) begin
                if (adc_index >= ADC_GROUPS || adc_delay != 0 || adc_rsp_valid) $fatal(1, "duplicate ADC request");
                if (array_enable || {array_id,row_start,row_count,input_bit,row_bits,column_start,column_count,2'b00}
                    !== adc_vectors[adc_index][71:24])
                    $fatal(1, "ADC routing/drive %0d got=%h expected=%h", adc_index,
                        {array_id,row_start,row_count,input_bit,row_bits,column_start,column_count,2'b00}, adc_vectors[adc_index][71:24]);
                pending_codes = sampled_codes;
                pending_error = (FAULT == 1 && adc_index == 0) || (FAULT == 7 && adc_index == ADC_GROUPS-1);
                adc_delay = 8 + ((STALL != 0) ? adc_index % 4 : 0);
                $fdisplay(events, "adc,%0d,%0d,%0d,%06h", run_index, cycle, adc_index, pending_codes);
                adc_index = adc_index + 1;
            end
            if (run_index >= 0 && !result_valid && !ready)
                $fdisplay(events, "state,%0d,%0d,%0d", run_index, cycle, debug_state);
        end
    end

    task automatic launch;
        @(negedge clk);
        board_base = 21'(board_address);
        neural_base = 21'(neural_address);
        hidden_shift = 6'(hidden_amount);
        logit_shift = 8'(logit_amount);
        if (FAULT == 3) board_base = board_base + 21'd1;
        if (FAULT == 4) neural_base = 21'd1572860;
        if (FAULT == 5) neural_base = board_base;
        if (!ready) $fatal(1, "start not ready");
        start = 1'b1;
        tick; start_cycle = cycle; immediate_result = result_valid;
        @(negedge clk); start = 1'b0;
        board_base = '1; neural_base = '1; hidden_shift = '1; logit_shift = -8'sd1;
    endtask

    initial begin
        if (!$value$plusargs("FIXTURE=%s", fixture) || !$value$plusargs("EVENTS=%s", events_path) ||
            !$value$plusargs("BOARD_BASE=%d", board_address) || !$value$plusargs("NEURAL_BASE=%d", neural_address) ||
            !$value$plusargs("HIDDEN_SHIFT=%d", hidden_amount) || !$value$plusargs("LOGIT_SHIFT=%d", logit_amount) ||
            !$value$plusargs("EXPECTED_VALUE=%d", expected_value)) $fatal(1, "fixture parameters required");
        $readmemh({fixture,"/initial.hex"}, memory);
        $readmemh({fixture,"/expected.hex"}, expected);
        $readmemh({fixture,"/adc.hex"}, adc_vectors);
        if (FAULT == 2) memory[(neural_address+((HIDDEN+3)/4)*4+28)/4] = '0;
        events = $fopen(events_path, "w");
        if (events == 0) $fatal(1, "cannot open events");
        if ($value$plusargs("VCD=%s", vcd_path)) begin
            $dumpfile(vcd_path); $dumpvars(1, tb_imc_buffered_neural_core);
        end
        tick; tick; rst_n = 1'b1;
        if (FAULT == 6) begin
            launch;
            while (!adc_rsp_ready) tick;
            tick;
            @(negedge clk); rst_n = 1'b0;
            tick; tick;
            if (!ready || result_valid || bank_valid != '0 || adc_req_valid) $fatal(1, "reset did not abort");
            rst_n = 1'b1;
        end
        expected_error = (FAULT == 1 || FAULT == 7) ? 3 : (FAULT == 2) ? 5 :
            (FAULT >= 3 && FAULT <= 5) ? 1 : 0;
        for (repeat_index = 0; repeat_index < REPEATS; repeat_index = repeat_index + 1) begin
            run_index = repeat_index;
            launch;
            while (!result_valid) tick;
            result_cycle = immediate_result ? start_cycle : cycle;
            if (result_error !== 4'(expected_error)) $fatal(1, "result error=%0d expected=%0d", result_error, expected_error);
            if (expected_error == 0) begin
                if (value_code !== 32'(expected_value) || adc_index != ADC_GROUPS) $fatal(1, "result value or ADC count");
                for (i = 0; i < RESULT_WORDS; i = i + 1)
                    if (memory[neural_address/4+i] !== expected[i])
                        $fatal(1, "SRAM result word %0d got=%h expected=%h", i, memory[neural_address/4+i], expected[i]);
            end else if (value_code !== '0) $fatal(1, "failed result must be zero");
            for (i = 0; i < 5; i = i + 1) begin
                tick;
                if (!result_valid || result_error !== 4'(expected_error) || bank_valid != '0 || adc_req_valid)
                    $fatal(1, "result backpressure");
                if (expected_error == 0 && value_code !== 32'(expected_value)) $fatal(1, "result changed under stall");
            end
            $fdisplay(events, "result,%0d,%0d,%0d,%0d,%0d", run_index, result_cycle,
                result_cycle-start_cycle, value_code, result_error);
            @(negedge clk); result_ready = 1'b1;
            tick;
            if (!ready || result_valid) $fatal(1, "result consumption");
            @(negedge clk); result_ready = 1'b0;
        end
        $fclose(events);
        $display("tb_imc_buffered_neural_core PASS"); $finish;
    end
endmodule
