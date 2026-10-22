// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_sram_router #(
    parameter int BANKS = 3,
    parameter int BANK_BYTE_W = 19,
    parameter int ADDR_W = 21
);
    localparam int WORD_W = BANK_BYTE_W-2;
    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic req_valid = 1'b0, req_ready, req_write = 1'b0;
    logic [ADDR_W-1:0] req_addr = '0;
    logic [31:0] req_wdata = '0;
    logic rsp_valid, rsp_ready = 1'b1, rsp_error;
    logic [31:0] rsp_rdata;
    logic [BANKS-1:0] bank_valid, bank_ready = '1, bank_write;
    logic [BANKS*WORD_W-1:0] bank_addr;
    logic [BANKS*32-1:0] bank_wdata;
    logic [BANKS-1:0] bank_rsp_valid = '0;
    logic [BANKS*32-1:0] bank_rdata = '0;
    integer i;
`ifdef IMC_POST_SYNTH
    imc_sram_router dut (.*);
`else
    imc_sram_router #(.BANKS(BANKS), .BANK_BYTE_W(BANK_BYTE_W), .ADDR_W(ADDR_W)) dut (.*);
`endif
    always #5 clk = ~clk;
    task automatic tick; @(posedge clk); #1; endtask
    task automatic issue(input logic [ADDR_W-1:0] address, input logic write_op);
        @(negedge clk);
        if (!req_ready) $fatal(1, "request blocked unexpectedly");
        req_valid = 1'b1; req_addr = address; req_write = write_op; req_wdata = 32'h12345678;
        tick;
        @(negedge clk); req_valid = 1'b0; req_addr = '1; req_wdata = '0;
    endtask
    initial begin
        tick; tick; rst_n = 1'b1;
        for (i = 0; i < BANKS; i = i + 1) begin
            bank_ready = '0;
            issue(ADDR_W'((i+1)*(2**BANK_BYTE_W)-4), 1'b1);
            if (bank_valid !== (BANKS'(1) << i) || !bank_write[i] ||
                bank_addr[i*WORD_W +: WORD_W] !== {WORD_W{1'b1}} ||
                bank_wdata[i*32 +: 32] !== 32'h12345678) $fatal(1, "bank decode/payload");
            tick; tick;
            if (req_ready || bank_valid !== (BANKS'(1) << i)) $fatal(1, "issue backpressure");
            @(negedge clk); bank_ready = '1;
            tick;
            if (bank_valid !== '0 || req_ready) $fatal(1, "duplicate issue or outstanding request lost");
            @(negedge clk); rsp_ready = 1'b0;
            bank_rsp_valid = BANKS'(1) << i; bank_rdata[i*32 +: 32] = 32'h87654321;
            #1;
            if (!rsp_valid || rsp_rdata !== 32'h87654321 || rsp_error) $fatal(1, "response route");
            tick;
            @(negedge clk); bank_rsp_valid = '0; bank_rdata = '0;
            tick; tick;
            if (!rsp_valid || rsp_rdata !== 32'h87654321 || req_ready) $fatal(1, "response hold");
            @(negedge clk); rsp_ready = 1'b1;
            tick;
            if (!req_ready || rsp_valid) $fatal(1, "response completion");
        end
        issue(ADDR_W'(BANKS*(2**BANK_BYTE_W)), 1'b0);
        if (!rsp_valid || !rsp_error || bank_valid !== '0) $fatal(1, "capacity violation");
        tick;
        issue(ADDR_W'(1), 1'b0);
        if (!rsp_valid || !rsp_error || bank_valid !== '0) $fatal(1, "misaligned request");
        tick;
        issue('0, 1'b0);
        if (bank_valid !== BANKS'(1) || bank_addr !== '0 || bank_write !== '0) $fatal(1, "root address zero");
        tick;
        @(negedge clk); bank_rsp_valid = BANKS'(1); bank_rdata[31:0] = 32'd42;
        req_valid = 1'b1; req_addr = ADDR_W'(4);
        #1;
        if (!rsp_valid || !req_ready || rsp_rdata !== 32'd42) $fatal(1, "two-cycle completion/new issue");
        tick;
        @(negedge clk); req_valid = 1'b0; bank_rsp_valid = '0;
        if (bank_valid !== BANKS'(1) || bank_addr[WORD_W-1:0] !== WORD_W'(1)) $fatal(1, "back-to-back request lost");
        rst_n = 1'b0; #1;
        if (bank_valid !== '0 || rsp_valid || !req_ready) $fatal(1, "reset failed");
        $display("tb_imc_sram_router PASS"); $finish;
    end
endmodule
