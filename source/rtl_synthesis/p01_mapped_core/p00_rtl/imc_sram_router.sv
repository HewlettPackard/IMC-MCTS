// SPDX-License-Identifier: MIT
// Route aligned 32-bit requests to a finite set of equal-capacity SRAM banks.
// One request outstanding. Bank issue follows acceptance by one clock edge.
// Responses pass through or occupy one holding register under backpressure.
// Reset must also reset the banks; invalid addresses complete without issue.
// PPA role: node_or_child_sram_bank_router
`default_nettype none
module imc_sram_router #(
    parameter int BANKS = 3,
    parameter int BANK_BYTE_W = 19,
    parameter int ADDR_W = 21
) (
    input  logic                              clk,
    input  logic                              rst_n,
    input  logic                              req_valid,
    output logic                              req_ready,
    input  logic [ADDR_W-1:0]                 req_addr,
    input  logic                              req_write,
    input  logic [31:0]                        req_wdata,
    output logic                              rsp_valid,
    input  logic                              rsp_ready,
    output logic                              rsp_error,
    output logic [31:0]                        rsp_rdata,
    output logic [BANKS-1:0]                  bank_valid,
    input  logic [BANKS-1:0]                  bank_ready,
    output logic [BANKS-1:0]                  bank_write,
    output logic [BANKS*(BANK_BYTE_W-2)-1:0]   bank_addr,
    output logic [BANKS*32-1:0]               bank_wdata,
    input  logic [BANKS-1:0]                  bank_rsp_valid,
    input  logic [BANKS*32-1:0]               bank_rdata
);
    localparam int BANK_ID_W = ADDR_W - BANK_BYTE_W;
    localparam int BANK_SEL_W = (BANKS > 1) ? $clog2(BANKS) : 1;
    localparam int WORD_ADDR_W = BANK_BYTE_W - 2;
    typedef enum logic [1:0] { ST_IDLE, ST_ISSUE, ST_WAIT, ST_HOLD } state_e;
    state_e state_q, state_d;
    logic [BANK_ID_W-1:0] bank_q, bank_d;
    logic [WORD_ADDR_W-1:0] address_q, address_d;
    logic write_q, write_d;
    logic [31:0] data_q, data_d, held_q, held_d;
    logic held_error_q, held_error_d;
    integer i;

    always_comb begin
        i = 0;
        state_d = state_q;
        bank_d = bank_q;
        address_d = address_q;
        write_d = write_q;
        data_d = data_q;
        held_d = held_q;
        held_error_d = held_error_q;
        bank_valid = '0;
        bank_write = '0;
        bank_addr = '0;
        bank_wdata = '0;
        rsp_valid = 1'b0;
        rsp_error = 1'b0;
        rsp_rdata = '0;
        req_ready = (state_q == ST_IDLE);
        unique case (state_q)
            ST_IDLE: begin
                state_d = ST_IDLE;
            end
            ST_ISSUE: begin
                for (i = 0; i < BANKS; i = i + 1) begin
                    if (bank_q == BANK_ID_W'(i)) begin
                        bank_valid[i] = 1'b1;
                        bank_write[i] = write_q;
                        bank_addr[i*WORD_ADDR_W +: WORD_ADDR_W] = address_q;
                        bank_wdata[i*32 +: 32] = data_q;
                        if (bank_ready[i])
                            state_d = ST_WAIT;
                    end
                end
            end
            ST_WAIT: begin
                if (int'(bank_q) < BANKS) begin
                    rsp_valid = bank_rsp_valid[BANK_SEL_W'(bank_q)];
                    rsp_rdata = bank_rdata[int'(bank_q)*32 +: 32];
                    if (rsp_valid) begin
                        held_d = rsp_rdata;
                        held_error_d = 1'b0;
                        if (rsp_ready)
                            state_d = ST_IDLE;
                        else
                            state_d = ST_HOLD;
                    end
                end
            end
            ST_HOLD: begin
                rsp_valid = 1'b1;
                rsp_error = held_error_q;
                rsp_rdata = held_q;
                if (rsp_ready)
                    state_d = ST_IDLE;
            end
            default: state_d = ST_IDLE;
        endcase
        if (rsp_valid && rsp_ready)
            req_ready = 1'b1;
        if (req_valid && req_ready) begin
            bank_d = req_addr[ADDR_W-1:BANK_BYTE_W];
            address_d = req_addr[BANK_BYTE_W-1:2];
            write_d = req_write;
            data_d = req_wdata;
            if (req_addr[1:0] != 2'b00 || int'(req_addr[ADDR_W-1:BANK_BYTE_W]) >= BANKS) begin
                held_d = '0;
                held_error_d = 1'b1;
                state_d = ST_HOLD;
            end else begin
                state_d = ST_ISSUE;
            end
        end
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q <= ST_IDLE;
            bank_q <= '0;
            address_q <= '0;
            write_q <= 1'b0;
            data_q <= '0;
            held_q <= '0;
            held_error_q <= 1'b0;
        end else begin
            state_q <= state_d;
            bank_q <= bank_d;
            address_q <= address_d;
            write_q <= write_d;
            data_q <= data_d;
            held_q <= held_d;
            held_error_q <= held_error_d;
        end
    end
endmodule
`default_nettype wire
