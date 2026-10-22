// SPDX-License-Identifier: MIT
// Two finite result banks with explicit capture, read and release ownership.
// Default: 32 16-bit ADC slots per bank and an eight-slot 128-bit readout.
// Banks remain occupied until release after accumulation, not merely readout.
// Capture to an occupied bank is rejected, including same-edge release.
// PPA role: two_result_register_banks_read_mux_and_ownership_control
`default_nettype none
module imc_parallel_result_banks #(
    parameter int WORD_BITS = 16,
    parameter int WORDS = 32,
    parameter int BUS_BITS = 128,
    parameter int COUNT_BITS = $clog2(WORDS+1),
    parameter int READ_BITS = ($clog2((WORDS*WORD_BITS+BUS_BITS-1)/BUS_BITS) > 0) ?
        $clog2((WORDS*WORD_BITS+BUS_BITS-1)/BUS_BITS) : 1
) (
    input  logic                        clk,
    input  logic                        rst_n,
    input  logic                        clear,
    input  logic                        capture_valid,
    input  logic                        capture_bank,
    input  logic [COUNT_BITS-1:0]       capture_count,
    input  logic [WORDS*WORD_BITS-1:0]  capture_data,
    output logic                        capture_ready,
    output logic                        capture_error,
    input  logic                        release_valid,
    input  logic                        release_bank,
    input  logic                        read_bank,
    input  logic [READ_BITS-1:0]        read_index,
    output logic [BUS_BITS-1:0]         read_data,
    output logic [BUS_BITS/WORD_BITS-1:0] read_slots_valid,
    output logic [1:0]                  occupied
);
    localparam int SLOTS = BUS_BITS/WORD_BITS;
    logic [WORDS*WORD_BITS-1:0] data_q [2], data_d [2];
    logic [COUNT_BITS-1:0] count_q [2], count_d [2];
    logic [1:0] occupied_d;
    logic error_d;
    integer i, j, slot;
    assign capture_ready = rst_n && !clear && !occupied[capture_bank];
    always_comb begin
        for (j = 0; j < 2; j = j + 1) begin
            data_d[j] = data_q[j];
            count_d[j] = count_q[j];
        end
        occupied_d = occupied;
        error_d = 1'b0;
        read_data = '0;
        read_slots_valid = '0;
        for (slot = 0; slot < SLOTS; slot = slot + 1) begin
            if (rst_n && occupied[read_bank] && int'(read_index)*SLOTS+slot < WORDS &&
                int'(read_index)*SLOTS+slot < int'(count_q[read_bank])) begin
                read_data[slot*WORD_BITS +: WORD_BITS] =
                    data_q[read_bank][(int'(read_index)*SLOTS+slot)*WORD_BITS +: WORD_BITS];
                read_slots_valid[slot] = 1'b1;
            end
        end
        if (clear) begin
            occupied_d = '0;
            for (j = 0; j < 2; j = j + 1) begin
                data_d[j] = '0;
                count_d[j] = '0;
            end
        end else begin
            if (release_valid) occupied_d[release_bank] = 1'b0;
            if (capture_valid) begin
                if (!capture_ready || capture_count == '0 || int'(capture_count) > WORDS)
                    error_d = 1'b1;
                else begin
                    data_d[capture_bank] = capture_data;
                    count_d[capture_bank] = capture_count;
                    occupied_d[capture_bank] = 1'b1;
                end
            end
        end
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            occupied <= '0;
            capture_error <= 1'b0;
            for (i = 0; i < 2; i = i + 1) begin
                data_q[i] <= '0;
                count_q[i] <= '0;
            end
        end else begin
            occupied <= occupied_d;
            capture_error <= error_d;
            for (i = 0; i < 2; i = i + 1) begin
                data_q[i] <= data_d[i];
                count_q[i] <= count_d[i];
            end
        end
    end
endmodule
`default_nettype wire
