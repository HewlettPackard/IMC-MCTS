// Sixteen concurrent, reordered UCB scorers with ordered, registered reduction.
// A batch contains one to sixteen visited children in original selection order.
// All operands are accepted together; SRAM loading is external and serialized.
// Equal scores keep the first child. Any arithmetic error invalidates the batch.
// Output is held until accepted; reset aborts the wrapper and every scorer.
// PPA role: sixteen_UCB_parents_plus_selection_dispatch_and_result_registers
// SPDX-License-Identifier: MIT
`default_nettype none
module imc_ucb_batch16_overlap #(
    parameter int LANES = 16,
    parameter int COUNT_BITS = $clog2(LANES+1),
    parameter int INDEX_BITS = (LANES > 1) ? $clog2(LANES) : 1
) (
    input  logic          clk,
    input  logic          rst_n,
    input  logic          batch_req_valid,
    output logic          batch_req_ready,
    input  logic [COUNT_BITS-1:0]    batch_count,
    input  logic [31:0]   batch_parent_visits,
    input  logic [63:0]   batch_exploration,
    input  logic [LANES*32-1:0]  batch_child_ids,
    input  logic [LANES*32-1:0]  batch_child_visits,
    input  logic [LANES*64-1:0]  batch_child_values,
    output logic          batch_rsp_valid,
    input  logic          batch_rsp_ready,
    output logic [31:0]   batch_rsp_child,
    output logic [63:0]   batch_rsp_score,
    output logic          batch_rsp_error,
    output logic [LANES-1:0]    debug_lane_active
);
    typedef enum logic [1:0] { ST_IDLE, ST_WAIT, ST_REDUCE, ST_RESULT } state_e;
    state_e state_q, state_d;
    logic [COUNT_BITS-1:0] count_q, count_d;
    logic [INDEX_BITS-1:0] index_q, index_d;
    logic [LANES*32-1:0] ids_q, ids_d;
    logic [LANES*64-1:0] scores_q, scores_d;
    logic [31:0] child_d;
    logic [63:0] score_d;
    logic error_d, all_valid;
    logic [LANES-1:0] lane_req_valid, lane_req_ready, lane_rsp_valid, lane_rsp_error;
    logic lane_rsp_ready;
    logic [LANES*64-1:0] lane_scores;
    logic [LANES*4-1:0] unused_lane_states;
    integer i;

    genvar lane;
    generate
        for (lane = 0; lane < LANES; lane = lane + 1) begin
            imc_ucb_score_overlap u_score (
                .clk(clk),
                .rst_n(rst_n),
                .score_req_valid(lane_req_valid[lane]),
                .score_req_ready(lane_req_ready[lane]),
                .score_parent_visits(batch_parent_visits),
                .score_child_visits(batch_child_visits[lane*32 +: 32]),
                .score_child_value(batch_child_values[lane*64 +: 64]),
                .score_exploration(batch_exploration),
                .score_rsp_valid(lane_rsp_valid[lane]),
                .score_rsp_ready(lane_rsp_ready),
                .score_rsp_value(lane_scores[lane*64 +: 64]),
                .score_rsp_error(lane_rsp_error[lane]),
                .debug_state(unused_lane_states[lane*4 +: 4])
            );
        end
    endgenerate

    assign batch_req_ready = rst_n && state_q == ST_IDLE && (&lane_req_ready);
    assign batch_rsp_valid = rst_n && state_q == ST_RESULT;
    assign lane_rsp_ready = state_q == ST_WAIT && all_valid;
    assign debug_lane_active = rst_n ? ~lane_req_ready : '0;

    always_comb begin
        lane_req_valid = '0;
        all_valid = 1'b1;
        for (i = 0; i < LANES; i = i + 1) begin
            lane_req_valid[i] = batch_req_valid && batch_req_ready &&
                batch_count != '0 && batch_count <= COUNT_BITS'(LANES) && COUNT_BITS'(i) < batch_count;
            if (COUNT_BITS'(i) < count_q && !lane_rsp_valid[i]) all_valid = 1'b0;
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
                if (batch_count == '0 || batch_count > COUNT_BITS'(LANES)) begin
                    error_d = 1'b1;
                    state_d = ST_RESULT;
                end
            end
            ST_WAIT: if (all_valid) begin
                scores_d = lane_scores;
                for (i = 0; i < LANES; i = i + 1)
                    if (COUNT_BITS'(i) < count_q && lane_rsp_error[i]) error_d = 1'b1;
                state_d = ST_REDUCE;
                if (error_d) state_d = ST_RESULT;
            end
            ST_REDUCE: begin
                if (index_q == '0 || scores_q[index_q*64 +: 64] > batch_rsp_score) begin
                    child_d = ids_q[index_q*32 +: 32];
                    score_d = scores_q[index_q*64 +: 64];
                end
                if (COUNT_BITS'(index_q) + COUNT_BITS'(1) == count_q) state_d = ST_RESULT;
                else index_d = index_q + INDEX_BITS'(1);
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
