// Four concurrent, reordered UCB scorers with ordered, registered reduction.
// A batch contains one to four visited children in original selection order.
// All operands are accepted together; SRAM loading is external and serialized.
// Equal scores keep the first child. Any arithmetic error invalidates the batch.
// Output is held until accepted; reset aborts the wrapper and every scorer.
// PPA role: four_UCB_parents_plus_selection_dispatch_and_result_registers
// SPDX-License-Identifier: MIT
`default_nettype none
module imc_ucb_batch_overlap (
    input  logic          clk,
    input  logic          rst_n,
    input  logic          batch_req_valid,
    output logic          batch_req_ready,
    input  logic [2:0]    batch_count,
    input  logic [31:0]   batch_parent_visits,
    input  logic [63:0]   batch_exploration,
    input  logic [127:0]  batch_child_ids,
    input  logic [127:0]  batch_child_visits,
    input  logic [255:0]  batch_child_values,
    output logic          batch_rsp_valid,
    input  logic          batch_rsp_ready,
    output logic [31:0]   batch_rsp_child,
    output logic [63:0]   batch_rsp_score,
    output logic          batch_rsp_error,
    output logic [3:0]    debug_lane_active
);
    typedef enum logic [1:0] { ST_IDLE, ST_WAIT, ST_REDUCE, ST_RESULT } state_e;
    state_e state_q, state_d;
    logic [2:0] count_q, count_d;
    logic [1:0] index_q, index_d;
    logic [127:0] ids_q, ids_d;
    logic [255:0] scores_q, scores_d;
    logic [31:0] child_d;
    logic [63:0] score_d;
    logic error_d, all_valid;
    logic [3:0] lane_req_valid, lane_req_ready, lane_rsp_valid, lane_rsp_error;
    logic lane_rsp_ready;
    logic [255:0] lane_scores;
    logic [15:0] unused_lane_states;
    integer i;

    imc_ucb_score_overlap u_score_a (
        .clk(clk), .rst_n(rst_n),
        .score_req_valid(lane_req_valid[0]), .score_req_ready(lane_req_ready[0]),
        .score_parent_visits(batch_parent_visits),
        .score_child_visits(batch_child_visits[0 +: 32]),
        .score_child_value(batch_child_values[0 +: 64]),
        .score_exploration(batch_exploration),
        .score_rsp_valid(lane_rsp_valid[0]), .score_rsp_ready(lane_rsp_ready),
        .score_rsp_value(lane_scores[0 +: 64]), .score_rsp_error(lane_rsp_error[0]),
        .debug_state(unused_lane_states[0 +: 4])
    );
    imc_ucb_score_overlap u_score_b (
        .clk(clk), .rst_n(rst_n),
        .score_req_valid(lane_req_valid[1]), .score_req_ready(lane_req_ready[1]),
        .score_parent_visits(batch_parent_visits),
        .score_child_visits(batch_child_visits[32 +: 32]),
        .score_child_value(batch_child_values[64 +: 64]),
        .score_exploration(batch_exploration),
        .score_rsp_valid(lane_rsp_valid[1]), .score_rsp_ready(lane_rsp_ready),
        .score_rsp_value(lane_scores[64 +: 64]), .score_rsp_error(lane_rsp_error[1]),
        .debug_state(unused_lane_states[4 +: 4])
    );
    imc_ucb_score_overlap u_score_c (
        .clk(clk), .rst_n(rst_n),
        .score_req_valid(lane_req_valid[2]), .score_req_ready(lane_req_ready[2]),
        .score_parent_visits(batch_parent_visits),
        .score_child_visits(batch_child_visits[64 +: 32]),
        .score_child_value(batch_child_values[128 +: 64]),
        .score_exploration(batch_exploration),
        .score_rsp_valid(lane_rsp_valid[2]), .score_rsp_ready(lane_rsp_ready),
        .score_rsp_value(lane_scores[128 +: 64]), .score_rsp_error(lane_rsp_error[2]),
        .debug_state(unused_lane_states[8 +: 4])
    );
    imc_ucb_score_overlap u_score_d (
        .clk(clk), .rst_n(rst_n),
        .score_req_valid(lane_req_valid[3]), .score_req_ready(lane_req_ready[3]),
        .score_parent_visits(batch_parent_visits),
        .score_child_visits(batch_child_visits[96 +: 32]),
        .score_child_value(batch_child_values[192 +: 64]),
        .score_exploration(batch_exploration),
        .score_rsp_valid(lane_rsp_valid[3]), .score_rsp_ready(lane_rsp_ready),
        .score_rsp_value(lane_scores[192 +: 64]), .score_rsp_error(lane_rsp_error[3]),
        .debug_state(unused_lane_states[12 +: 4])
    );

    assign batch_req_ready = rst_n && state_q == ST_IDLE && (&lane_req_ready);
    assign batch_rsp_valid = rst_n && state_q == ST_RESULT;
    assign lane_rsp_ready = state_q == ST_WAIT && all_valid;
    assign debug_lane_active = rst_n ? ~lane_req_ready : 4'd0;

    always_comb begin
        lane_req_valid = '0;
        all_valid = 1'b1;
        for (i = 0; i < 4; i = i + 1) begin
            lane_req_valid[i] = batch_req_valid && batch_req_ready &&
                batch_count != '0 && batch_count <= 3'd4 && 3'(i) < batch_count;
            if (3'(i) < count_q && !lane_rsp_valid[i]) all_valid = 1'b0;
        end
        state_d = state_q;
        count_d = count_q;
        index_d = index_q;
        ids_d = ids_q;
        scores_d = scores_q;
        child_d = batch_rsp_child;
        score_d = batch_rsp_score;
        error_d = batch_rsp_error;
        unique case (state_q)
            ST_IDLE: if (batch_req_valid && batch_req_ready) begin
                count_d = batch_count;
                ids_d = batch_child_ids;
                index_d = '0;
                scores_d = '0;
                child_d = '0;
                score_d = '0;
                error_d = 1'b0;
                state_d = ST_WAIT;
                if (batch_count == '0 || batch_count > 3'd4) begin
                    error_d = 1'b1;
                    state_d = ST_RESULT;
                end
            end
            ST_WAIT: if (all_valid) begin
                scores_d = lane_scores;
                for (i = 0; i < 4; i = i + 1)
                    if (3'(i) < count_q && lane_rsp_error[i]) error_d = 1'b1;
                state_d = ST_REDUCE;
                if (error_d) state_d = ST_RESULT;
            end
            ST_REDUCE: begin
                if (index_q == '0 || scores_q[index_q*64 +: 64] > batch_rsp_score) begin
                    child_d = ids_q[index_q*32 +: 32];
                    score_d = scores_q[index_q*64 +: 64];
                end
                if ({1'b0, index_q} + 3'd1 == count_q) state_d = ST_RESULT;
                else index_d = index_q + 2'd1;
            end
            ST_RESULT: if (batch_rsp_ready) state_d = ST_IDLE;
            default: begin
                error_d = 1'b1;
                state_d = ST_RESULT;
            end
        endcase
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q <= ST_IDLE;
            count_q <= '0;
            index_q <= '0;
            ids_q <= '0;
            scores_q <= '0;
            batch_rsp_child <= '0;
            batch_rsp_score <= '0;
            batch_rsp_error <= 1'b0;
        end else begin
            state_q <= state_d;
            count_q <= count_d;
            index_q <= index_d;
            ids_q <= ids_d;
            scores_q <= scores_d;
            batch_rsp_child <= child_d;
            batch_rsp_score <= score_d;
            batch_rsp_error <= error_d;
        end
    end
endmodule
`default_nettype wire
