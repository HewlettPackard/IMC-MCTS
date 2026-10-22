// SPDX-License-Identifier: MIT
// Serialized six-word node headers feed two candidate banks and sixteen UCB lanes.
// A load reserves one bank; six accepted 32-bit words per child publish the group.
// Header words 0..2 are visits and binary64 value; words 3..5 are consumed, discarded.
// child_id is sampled with word 0. Dispatch reads the complete bank without a copy.
// A dispatched bank remains owned until the UCB response is accepted. Reset aborts all.
// PPA role: connected_selector_operand_storage_loader_and_ucb16
`default_nettype none
module imc_selection_path (
    input  logic          clk,
    input  logic          rst_n,
    input  logic          load_valid,
    output logic          load_ready,
    input  logic          load_bank,
    input  logic [4:0]    load_count,
    input  logic          word_valid,
    output logic          word_ready,
    input  logic [31:0]   child_id,
    input  logic [31:0]   header_word,
    output logic          load_error,
    input  logic          dispatch_valid,
    output logic          dispatch_ready,
    input  logic          dispatch_bank,
    input  logic [31:0]   parent_visits,
    input  logic [63:0]   exploration,
    output logic          rsp_valid,
    input  logic          rsp_ready,
    output logic [31:0]   rsp_child,
    output logic [63:0]   rsp_score,
    output logic          rsp_error,
    output logic [1:0]    occupied,
    output logic [15:0]   debug_lane_active
);
    logic [2047:0] data_q [2], data_d [2];
    logic [4:0] count_q [2], count_d [2];
    logic [1:0] occupied_d, published_q, published_d;
    logic loading_q, loading_d, load_bank_q, load_bank_d;
    logic [3:0] slot_q, slot_d;
    logic [2:0] word_q, word_d;
    logic scoring_q, scoring_d, score_bank_q, score_bank_d;
    logic error_d, batch_ready, batch_valid;
    logic [511:0] child_ids, child_visits;
    logic [1023:0] child_values;
    integer i, j;

    assign load_ready = rst_n && !loading_q && !occupied[load_bank];
    assign word_ready = rst_n && loading_q;
    assign dispatch_ready = rst_n && !scoring_q && published_q[dispatch_bank] && batch_ready;
    assign batch_valid = dispatch_valid && dispatch_ready;

    imc_ucb_batch16_overlap u_batch (
        .clk(clk),
        .rst_n(rst_n),
        .batch_req_valid(batch_valid),
        .batch_req_ready(batch_ready),
        .batch_count(count_q[dispatch_bank]),
        .batch_parent_visits(parent_visits),
        .batch_exploration(exploration),
        .batch_child_ids(child_ids),
        .batch_child_visits(child_visits),
        .batch_child_values(child_values),
        .batch_rsp_valid(rsp_valid),
        .batch_rsp_ready(rsp_ready),
        .batch_rsp_child(rsp_child),
        .batch_rsp_score(rsp_score),
        .batch_rsp_error(rsp_error),
        .debug_lane_active(debug_lane_active)
    );

    always_comb begin
        for (j = 0; j < 2; j = j + 1) begin
            data_d[j] = data_q[j];
            count_d[j] = count_q[j];
        end
        for (j = 0; j < 16; j = j + 1) begin
            child_ids[j*32 +: 32] = data_q[dispatch_bank][j*128 +: 32];
            child_visits[j*32 +: 32] = data_q[dispatch_bank][j*128+32 +: 32];
            child_values[j*64 +: 64] = data_q[dispatch_bank][j*128+64 +: 64];
        end
        occupied_d = occupied;
        published_d = published_q;
        loading_d = loading_q;
        load_bank_d = load_bank_q;
        slot_d = slot_q;
        word_d = word_q;
        scoring_d = scoring_q;
        score_bank_d = score_bank_q;
        error_d = 1'b0;
        if (load_valid && load_ready) begin
            if (load_count == '0 || load_count > 5'd16) error_d = 1'b1;
            else begin
                loading_d = 1'b1;
                load_bank_d = load_bank;
                slot_d = '0;
                word_d = '0;
                count_d[load_bank] = load_count;
                data_d[load_bank] = '0;
                occupied_d[load_bank] = 1'b1;
                published_d[load_bank] = 1'b0;
            end
        end
        if (word_valid && word_ready) begin
            unique case (word_q)
                3'd0: begin
                    data_d[load_bank_q][int'(slot_q)*128 +: 32] = child_id;
                    data_d[load_bank_q][int'(slot_q)*128+32 +: 32] = header_word;
                end
                3'd1: data_d[load_bank_q][int'(slot_q)*128+64 +: 32] = header_word;
                3'd2: data_d[load_bank_q][int'(slot_q)*128+96 +: 32] = header_word;
                default: begin end
            endcase
            if (word_q == 3'd5) begin
                word_d = '0;
                if (5'(slot_q) + 5'd1 == count_q[load_bank_q]) begin
                    loading_d = 1'b0;
                    published_d[load_bank_q] = 1'b1;
                end else slot_d = slot_q + 4'd1;
            end else word_d = word_q + 3'd1;
        end
        if (batch_valid) begin
            scoring_d = 1'b1;
            score_bank_d = dispatch_bank;
        end
        if (scoring_q && rsp_valid && rsp_ready) begin
            scoring_d = 1'b0;
            published_d[score_bank_q] = 1'b0;
            occupied_d[score_bank_q] = 1'b0;
        end
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (i = 0; i < 2; i = i + 1) begin
                data_q[i] <= '0;
                count_q[i] <= '0;
            end
            occupied <= '0;
            published_q <= '0;
            loading_q <= 1'b0;
            load_bank_q <= 1'b0;
            slot_q <= '0;
            word_q <= '0;
            scoring_q <= 1'b0;
            score_bank_q <= 1'b0;
            load_error <= 1'b0;
        end else begin
            for (i = 0; i < 2; i = i + 1) begin
                data_q[i] <= data_d[i];
                count_q[i] <= count_d[i];
            end
            occupied <= occupied_d;
            published_q <= published_d;
            loading_q <= loading_d;
            load_bank_q <= load_bank_d;
            slot_q <= slot_d;
            word_q <= word_d;
            scoring_q <= scoring_d;
            score_bank_q <= score_bank_d;
            load_error <= error_d;
        end
    end
endmodule
`default_nettype wire
