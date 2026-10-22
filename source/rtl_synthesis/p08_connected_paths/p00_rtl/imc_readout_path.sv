// SPDX-License-Identifier: MIT
// Two ADC result banks feed a 128-bit bus, 512-bit group staging and eight ALUs.
// Consumption is four or fewer read edges then four or fewer add edges, never overlapped.
// Groups use an eight-aligned column base in the 96-word accumulator space.
// advance stalls reads and writes together. Invalid group metadata preserves the bank.
// The bank is released only on the final add edge; response metadata holds under stall.
// PPA role: connected_neural_result_storage_staging_and_accumulation
`default_nettype none
module imc_readout_path (
    input  logic         clk,
    input  logic         rst_n,
    input  logic         clear,
    input  logic         advance,
    input  logic         capture_valid,
    input  logic         capture_bank,
    input  logic [5:0]   capture_count,
    input  logic [511:0] capture_data,
    output logic         capture_ready,
    output logic         capture_error,
    input  logic         group_valid,
    output logic         group_ready,
    input  logic         group_bank,
    input  logic [5:0]   group_count,
    input  logic [6:0]   column_base,
    input  logic [3:0]   input_shift,
    output logic         rsp_valid,
    input  logic         rsp_ready,
    output logic         rsp_error,
    output logic [1:0]   occupied,
    input  logic [31:0]  read_addr,
    output logic [255:0] read_data,
    output logic         debug_bus_valid,
    output logic [1:0]   debug_bus_index,
    output logic [127:0] debug_bus_data,
    output logic [7:0]   debug_bus_mask,
    output logic [7:0]   debug_cmd_valid,
    output logic [31:0]  debug_cmd_addr,
    output logic [95:0]  debug_adc_code,
    output logic [7:0]   debug_cmd_done,
    output logic [7:0]   debug_cmd_error,
    output logic         debug_release
);
    typedef enum logic [1:0] { ST_IDLE, ST_READ, ST_ADD, ST_RESULT } state_e;
    state_e state_q, state_d;
    logic [511:0] stage_q, stage_d;
    logic bank_q, bank_d;
    logic [5:0] count_q, count_d;
    logic [5:0] bank_count_q [2], bank_count_d [2];
    logic [6:0] base_q, base_d;
    logic [3:0] shift_q, shift_d;
    logic [1:0] beat_q, beat_d;
    logic error_q, error_d;
    logic read_bank, release_bank;
    logic [1:0] read_index;
    logic [127:0] bus_data;
    logic [7:0] bus_mask;
    logic [31:0] shift_amount;
    logic metadata_ok, start_group, result_accept;
    integer i, j;
    genvar lane;

    assign result_accept = state_q == ST_RESULT && rsp_ready;
    assign group_ready = rst_n && !clear && advance &&
        (state_q == ST_IDLE || result_accept) && occupied[group_bank];
    assign start_group = group_valid && group_ready;
    assign metadata_ok = group_count != '0 && group_count <= 6'd32 &&
        group_count == bank_count_q[group_bank] && column_base[2:0] == '0 &&
        (8'(column_base) + 8'(group_count)) <= 8'd96;
    assign rsp_valid = rst_n && !clear && state_q == ST_RESULT;
    assign rsp_error = error_q || debug_cmd_error != '0;
    assign debug_bus_data = bus_data;
    assign debug_bus_mask = bus_mask;
    assign debug_bus_index = read_index;
    assign release_bank = bank_q;
    assign debug_release = rst_n && !clear && advance && state_q == ST_ADD &&
        (int'(beat_q)+1)*8 >= int'(count_q);
    generate
        for (lane = 0; lane < 8; lane = lane + 1) begin: g_command
            assign debug_cmd_valid[lane] = rst_n && !clear && advance &&
                state_q == ST_ADD && int'(beat_q)*8+lane < int'(count_q);
            assign debug_cmd_addr[lane*4 +: 4] = debug_cmd_valid[lane] ?
                4'((int'(base_q)+int'(beat_q)*8+lane)/8) : 4'b0;
            assign debug_adc_code[lane*12 +: 12] = debug_cmd_valid[lane] ?
                stage_q[(int'(beat_q)*8+lane)*16 +: 12] : 12'b0;
            assign shift_amount[lane*4 +: 4] = shift_q;
        end
    endgenerate
    assign read_bank = start_group && metadata_ok ? group_bank : bank_q;
    assign read_index = start_group && metadata_ok ? 2'b0 : beat_q;

    imc_parallel_result_banks u_results (
        .clk(clk),
        .rst_n(rst_n),
        .clear(clear),
        .capture_valid(capture_valid),
        .capture_bank(capture_bank),
        .capture_count(capture_count),
        .capture_data(capture_data),
        .capture_ready(capture_ready),
        .capture_error(capture_error),
        .release_valid(debug_release),
        .release_bank(release_bank),
        .read_bank(read_bank),
        .read_index(read_index),
        .read_data(bus_data),
        .read_slots_valid(bus_mask),
        .occupied(occupied)
    );
    imc_parallel_accumulators u_accumulators (
        .clk(clk),
        .rst_n(rst_n),
        .clear(clear),
        .cmd_valid(debug_cmd_valid),
        .cmd_addr(debug_cmd_addr),
        .adc_code(debug_adc_code),
        .shift_amount(shift_amount),
        .subtract(8'b0),
        .read_addr(read_addr),
        .read_data(read_data),
        .cmd_done(debug_cmd_done),
        .cmd_error(debug_cmd_error)
    );

    always_comb begin
        state_d = state_q;
        stage_d = stage_q;
        bank_d = bank_q;
        count_d = count_q;
        base_d = base_q;
        shift_d = shift_q;
        beat_d = beat_q;
        error_d = error_q;
        for (j = 0; j < 2; j = j + 1) bank_count_d[j] = bank_count_q[j];
        debug_bus_valid = 1'b0;
        if (clear) begin
            state_d = ST_IDLE;
            stage_d = '0;
            bank_d = 1'b0;
            count_d = '0;
            base_d = '0;
            shift_d = '0;
            beat_d = '0;
            error_d = 1'b0;
            for (j = 0; j < 2; j = j + 1) bank_count_d[j] = '0;
        end else begin
            if (capture_valid && capture_ready && capture_count != '0 && capture_count <= 6'd32)
                bank_count_d[capture_bank] = capture_count;
            if (result_accept) state_d = ST_IDLE;
            if (start_group) begin
                error_d = !metadata_ok;
                if (!metadata_ok) state_d = ST_RESULT;
                else begin
                    debug_bus_valid = 1'b1;
                    stage_d = '0;
                    stage_d[0 +: 128] = bus_data;
                    bank_d = group_bank;
                    count_d = group_count;
                    base_d = column_base;
                    shift_d = input_shift;
                    beat_d = 2'd1;
                    if (group_count <= 6'd8) begin
                        state_d = ST_ADD;
                        beat_d = '0;
                    end else state_d = ST_READ;
                end
            end else begin
                unique case (state_q)
                    ST_READ: if (advance) begin
                        debug_bus_valid = 1'b1;
                        stage_d[int'(beat_q)*128 +: 128] = bus_data;
                        if ((int'(beat_q)+1)*8 >= int'(count_q)) begin
                            beat_d = '0;
                            state_d = ST_ADD;
                        end else beat_d = beat_q + 2'd1;
                    end
                    ST_ADD: if (advance) begin
                        if ((int'(beat_q)+1)*8 >= int'(count_q)) begin
                            bank_count_d[bank_q] = '0;
                            state_d = ST_RESULT;
                            beat_d = '0;
                        end else beat_d = beat_q + 2'd1;
                    end
                    default: begin end
                endcase
            end
            if (debug_cmd_error != '0 && state_q == ST_ADD) error_d = 1'b1;
        end
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q <= ST_IDLE;
            stage_q <= '0;
            bank_q <= 1'b0;
            count_q <= '0;
            base_q <= '0;
            shift_q <= '0;
            beat_q <= '0;
            error_q <= 1'b0;
            for (i = 0; i < 2; i = i + 1) bank_count_q[i] <= '0;
        end else begin
            state_q <= state_d;
            stage_q <= stage_d;
            bank_q <= bank_d;
            count_q <= count_d;
            base_q <= base_d;
            shift_q <= shift_d;
            beat_q <= beat_d;
            error_q <= error_d;
            for (i = 0; i < 2; i = i + 1) bank_count_q[i] <= bank_count_d[i];
        end
    end
endmodule
`default_nettype wire
