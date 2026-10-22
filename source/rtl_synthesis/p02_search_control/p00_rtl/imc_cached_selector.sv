// Traverse packed tree SRAM through a bounded FIFO parent-link CAM cache.
// One selection owns memory/CAM/score interfaces through held completion.
// Full child output precedes scoring; first unvisited and first tied child win.
// Runtime errors poison the operation until coordinated memory/CAM reset.
// PPA role: cached_selection_control_without_cam_or_score_arithmetic
// SPDX-License-Identifier: MIT
`default_nettype none

module imc_cached_selector #(
    parameter int BOARD_SIZE = 9,
    parameter int CAM_ENTRIES = 1024,
    parameter int NEURAL_BYTES = 16512,
    parameter int ADDR_W = 21,
    parameter int NODE_BYTES = 1572864,
    parameter int CHILD_BYTES = 524288,
    parameter int ROW_W = (CAM_ENTRIES < 2) ? 1 : $clog2(CAM_ENTRIES),
    parameter int ROW_COUNT_W = $clog2(CAM_ENTRIES + 1)
) (
    input  logic                       clk,
    input  logic                       rst_n,
    input  logic                       start,
    output logic                       ready,
    input  logic [31:0]                root_id,
    input  logic [31:0]                nodes_used,
    input  logic [31:0]                edges_used,
    input  logic [31:0]                path_limit,
    input  logic [63:0]                exploration_constant,
    output logic                       result_valid,
    input  logic                       result_ready,
    output logic [31:0]                leaf_id,
    output logic [31:0]                path_depth,
    output logic [3:0]                 result_error,
    output logic                       poisoned,
    output logic                       node_req_valid,
    input  logic                       node_req_ready,
    output logic                       node_req_write,
    output logic [ADDR_W-1:0]          node_req_addr,
    output logic [31:0]                node_req_wdata,
    input  logic                       node_rsp_valid,
    output logic                       node_rsp_ready,
    input  logic [31:0]                node_rsp_rdata,
    input  logic                       node_rsp_error,
    output logic                       child_req_valid,
    input  logic                       child_req_ready,
    output logic [ADDR_W-1:0]          child_req_addr,
    input  logic                       child_rsp_valid,
    output logic                       child_rsp_ready,
    input  logic [31:0]                child_rsp_rdata,
    input  logic                       child_rsp_error,
    output logic                       cam_req_valid,
    input  logic                       cam_req_ready,
    output logic [1:0]                 cam_req_op,
    output logic [ROW_W-1:0]           cam_req_row,
    output logic [31:0]                cam_req_parent,
    output logic [31:0]                cam_req_child,
    input  logic                       cam_rsp_valid,
    output logic                       cam_rsp_ready,
    input  logic                       cam_rsp_error,
    input  logic [CAM_ENTRIES-1:0]     cam_rsp_matches,
    input  logic [31:0]                cam_rsp_parent,
    input  logic [31:0]                cam_rsp_child,
    input  logic                       cam_rsp_row_valid,
    output logic                       score_req_valid,
    input  logic                       score_req_ready,
    output logic [31:0]                score_parent_visits,
    output logic [31:0]                score_child_visits,
    output logic [63:0]                score_child_value,
    output logic [63:0]                score_exploration,
    input  logic                       score_rsp_valid,
    output logic                       score_rsp_ready,
    input  logic [63:0]                score_rsp_value,
    input  logic                       score_rsp_error,
    output logic [5:0]                 debug_state,
    output logic [ROW_COUNT_W-1:0]     cache_rows_used,
    output logic [ROW_W-1:0]           cache_row_head,
    output logic [ROW_W-1:0]           cache_row_tail
);
    localparam int MAX_CHILDREN = BOARD_SIZE * BOARD_SIZE;
    localparam int CHILD_W = (MAX_CHILDREN < 2) ? 1 : $clog2(MAX_CHILDREN);
    localparam int PATH_CAPACITY = MAX_CHILDREN + 1;
    localparam int BOARD_BYTES = 4 * ((2 * MAX_CHILDREN + 31) / 32);
    localparam int NODE_STRIDE = 24 + BOARD_BYTES;
    localparam int STATS_BASE = 4 * PATH_CAPACITY + BOARD_BYTES;
    localparam int CACHE_BASE = STATS_BASE + 16;
    localparam int NODE_BASE = CACHE_BASE + 16 * CAM_ENTRIES + NEURAL_BYTES;
    localparam int NODE_CAPACITY = (NODE_BYTES - NODE_BASE) / NODE_STRIDE;
    localparam logic CONFIG_OK = BOARD_SIZE > 0 && MAX_CHILDREN <= 65535 &&
        CAM_ENTRIES >= MAX_CHILDREN && CAM_ENTRIES <= 32768 &&
        NODE_BASE >= 0 && NODE_BASE + NODE_STRIDE <= NODE_BYTES &&
        NODE_BYTES <= (2**ADDR_W) && CHILD_BYTES <= (2**ADDR_W);

    typedef enum logic [5:0] {
        ST_IDLE, ST_NODE_READ, ST_NODE_CHECK, ST_PATH_DONE,
        ST_SEARCH, ST_SEARCH_DONE, ST_EVICT, ST_EVICT_HEADER,
        ST_EVICT_ROW, ST_EVICT_NEXT, ST_FILL, ST_FILL_CHILD,
        ST_FILL_ACK, ST_HEADER_WRITE, ST_FLAGS_WRITE, ST_REFILL_SEARCH,
        ST_READ_HEADER, ST_CHECK_HEADER, ST_COLLECT, ST_COLLECT_DONE,
        ST_CANDIDATE, ST_STAGE, ST_READ_STAGE, ST_SCORE, ST_SCORE_DONE,
        ST_MEMORY_REQ, ST_MEMORY_WAIT, ST_CAM_REQ, ST_CAM_WAIT,
        ST_SCORE_REQ, ST_SCORE_WAIT, ST_RESULT
    } state_e;
    typedef enum logic [1:0] { CAM_SEARCH, CAM_FILL, CAM_INVALIDATE, CAM_READ } cam_op_e;

    state_e state_q, state_d, memory_resume_q, memory_resume_d, cam_resume_q, cam_resume_d;
    cam_op_e cam_op_q, cam_op_d;
    logic [31:0] node_q, node_d, allocated_nodes_q, allocated_nodes_d;
    logic [31:0] allocated_edges_q, allocated_edges_d, path_limit_q, path_limit_d;
    logic [31:0] depth_d, parent_visits_q, parent_visits_d, child_start_q, child_start_d;
    logic [15:0] child_count_q, child_count_d, header_slot_q, header_slot_d;
    logic player_q, player_d, poison_d;
    logic [3:0] error_d;
    logic [63:0] exploration_q, exploration_d;
    logic [ROW_W-1:0] row_head_q, row_head_d, row_tail_q, row_tail_d;
    logic [ROW_W-1:0] header_head_q, header_head_d, header_tail_q, header_tail_d;
    logic [ROW_COUNT_W-1:0] rows_used_q, rows_used_d, groups_q, groups_d;
    logic [ROW_W-1:0] row_q, row_d, first_row_q, first_row_d;
    logic [15:0] count_q, count_d, index_q, index_d;
    logic [CAM_ENTRIES-1:0] matches_q, matches_d;
    logic [31:0] child_ids_q [0:MAX_CHILDREN-1];
    logic [31:0] child_ids_d [0:MAX_CHILDREN-1];
    logic [31:0] candidate_q, candidate_d, visits_q, visits_d;
    logic [63:0] value_q, value_d, score_q, score_d, best_score_q, best_score_d;
    logic [31:0] best_child_q, best_child_d;
    logic best_valid_q, best_valid_d, better;
    logic memory_child_q, memory_child_d, memory_write_q, memory_write_d;
    logic [ADDR_W-1:0] memory_base_q, memory_base_d;
    logic [2:0] memory_words_q, memory_words_d, memory_index_q, memory_index_d;
    logic [191:0] buffer_q, buffer_d;
    logic [31:0] cam_child_q, cam_child_d, cam_parent_q, cam_parent_d;
    logic cam_valid_q, cam_valid_d;
    logic [31:0] memory_data;
    logic memory_ready, memory_valid, memory_error;
    logic [32:0] child_end;
    integer i, j;

    assign ready = rst_n && state_q == ST_IDLE;
    assign result_valid = rst_n && state_q == ST_RESULT;
    assign leaf_id = node_q;
    assign debug_state = state_q;
    assign cache_rows_used = rows_used_q;
    assign cache_row_head = row_head_q;
    assign cache_row_tail = row_tail_q;
    assign node_req_valid = rst_n && state_q == ST_MEMORY_REQ && !memory_child_q;
    assign node_req_write = memory_write_q;
    assign node_req_addr = memory_base_q + (ADDR_W'(memory_index_q) << 2);
    assign node_req_wdata = memory_index_q < 3'd6 ? buffer_q[int'(memory_index_q)*32 +: 32] : 32'd0;
    assign node_rsp_ready = rst_n && state_q == ST_MEMORY_WAIT && !memory_child_q;
    assign child_req_valid = rst_n && state_q == ST_MEMORY_REQ && memory_child_q;
    assign child_req_addr = node_req_addr;
    assign child_rsp_ready = rst_n && state_q == ST_MEMORY_WAIT && memory_child_q;
    assign memory_ready = memory_child_q ? child_req_ready : node_req_ready;
    assign memory_valid = memory_child_q ? child_rsp_valid : node_rsp_valid;
    assign memory_data = memory_child_q ? child_rsp_rdata : node_rsp_rdata;
    assign memory_error = memory_child_q ? child_rsp_error : node_rsp_error;
    assign cam_req_valid = rst_n && state_q == ST_CAM_REQ;
    assign cam_req_op = cam_op_q;
    assign cam_req_row = row_q;
    assign cam_req_parent = node_q;
    assign cam_req_child = cam_child_q;
    assign cam_rsp_ready = rst_n && state_q == ST_CAM_WAIT;
    assign score_req_valid = rst_n && state_q == ST_SCORE_REQ;
    assign score_parent_visits = parent_visits_q;
    assign score_child_visits = visits_q;
    assign score_child_value = value_q;
    assign score_exploration = exploration_q;
    assign score_rsp_ready = rst_n && state_q == ST_SCORE_WAIT;
    assign child_end = {1'b0, child_start_q} + {17'd0, child_count_q};
    assign better = !best_valid_q || ((score_q[62:0] == '0 && best_score_q[62:0] == '0) ? 1'b0 :
        ((score_q[63] != best_score_q[63]) ? !score_q[63] :
        (score_q[63] ? score_q[62:0] < best_score_q[62:0] : score_q[62:0] > best_score_q[62:0])));

    always_comb begin
        state_d = state_q;
        memory_resume_d = memory_resume_q;
        cam_resume_d = cam_resume_q;
        cam_op_d = cam_op_q;
        node_d = node_q;
        allocated_nodes_d = allocated_nodes_q;
        allocated_edges_d = allocated_edges_q;
        path_limit_d = path_limit_q;
        depth_d = path_depth;
        parent_visits_d = parent_visits_q;
        child_start_d = child_start_q;
        child_count_d = child_count_q;
        header_slot_d = header_slot_q;
        player_d = player_q;
        poison_d = poisoned;
        error_d = result_error;
        exploration_d = exploration_q;
        row_head_d = row_head_q;
        row_tail_d = row_tail_q;
        header_head_d = header_head_q;
        header_tail_d = header_tail_q;
        rows_used_d = rows_used_q;
        groups_d = groups_q;
        row_d = row_q;
        first_row_d = first_row_q;
        count_d = count_q;
        index_d = index_q;
        matches_d = matches_q;
        for (i = 0; i < MAX_CHILDREN; i = i + 1) child_ids_d[i] = child_ids_q[i];
        candidate_d = candidate_q;
        visits_d = visits_q;
        value_d = value_q;
        score_d = score_q;
        best_score_d = best_score_q;
        best_child_d = best_child_q;
        best_valid_d = best_valid_q;
        memory_child_d = memory_child_q;
        memory_write_d = memory_write_q;
        memory_base_d = memory_base_q;
        memory_words_d = memory_words_q;
        memory_index_d = memory_index_q;
        buffer_d = buffer_q;
        cam_child_d = cam_child_q;
        cam_parent_d = cam_parent_q;
        cam_valid_d = cam_valid_q;

        unique case (state_q)
            ST_IDLE: begin
                if (start) begin
                    node_d = root_id;
                    allocated_nodes_d = nodes_used;
                    allocated_edges_d = edges_used;
                    path_limit_d = path_limit;
                    exploration_d = exploration_constant;
                    depth_d = '0;
                    error_d = '0;
                    state_d = ST_NODE_READ;
                    if (poisoned) begin
                        error_d = 4'd8;
                        state_d = ST_RESULT;
                    end else if (!CONFIG_OK || nodes_used == '0 || nodes_used > 32'(NODE_CAPACITY) ||
                            root_id >= nodes_used || edges_used > 32'(CHILD_BYTES/4) ||
                            path_limit == '0 || path_limit > 32'(PATH_CAPACITY) ||
                            exploration_constant[63] || exploration_constant[62:52] == 11'h7ff) begin
                        error_d = 4'd1;
                        state_d = ST_RESULT;
                    end
                end
            end
            ST_NODE_READ: begin
                memory_child_d = 1'b0;
                memory_write_d = 1'b0;
                memory_base_d = ADDR_W'(NODE_BASE) + ADDR_W'(node_q) * ADDR_W'(NODE_STRIDE);
                memory_words_d = 3'd6;
                memory_resume_d = ST_NODE_CHECK;
                state_d = ST_MEMORY_REQ;
                if (node_q >= allocated_nodes_q) begin
                    error_d = 4'd1;
                    state_d = ST_RESULT;
                    poison_d = 1'b1;
                end
            end
            ST_NODE_CHECK: begin
                parent_visits_d = buffer_q[31:0];
                child_start_d = buffer_q[159:128];
                child_count_d = buffer_q[175:160];
                header_slot_d = {1'b0, buffer_q[191:177]};
                player_d = buffer_q[176];
                memory_child_d = 1'b0;
                memory_write_d = 1'b1;
                memory_base_d = ADDR_W'(path_depth) << 2;
                memory_words_d = 3'd1;
                buffer_d[31:0] = node_q;
                memory_resume_d = ST_PATH_DONE;
                state_d = ST_MEMORY_REQ;
                if (path_depth >= path_limit_q) begin
                    error_d = 4'd6;
                    state_d = ST_RESULT;
                    poison_d = 1'b1;
                end
            end
            ST_PATH_DONE: begin
                depth_d = path_depth + 32'd1;
                state_d = ST_SEARCH;
                if (child_count_q == '0 || parent_visits_q == '0) state_d = ST_RESULT;
                else if (child_count_q > 16'(MAX_CHILDREN) || child_end > {1'b0, allocated_edges_q}) begin
                    error_d = 4'd1;
                    state_d = ST_RESULT;
                    poison_d = 1'b1;
                end
            end
            ST_SEARCH: begin
                cam_op_d = CAM_SEARCH;
                cam_resume_d = ST_SEARCH_DONE;
                state_d = ST_CAM_REQ;
            end
            ST_SEARCH_DONE: begin
                if (matches_q == '0) state_d = ST_EVICT;
                else state_d = ST_READ_HEADER;
            end
            ST_EVICT: begin
                if (32'(rows_used_q) + 32'(child_count_q) <= 32'(CAM_ENTRIES)) begin
                    index_d = '0;
                    first_row_d = row_tail_q;
                    header_slot_d = 16'(header_tail_q);
                    state_d = ST_FILL;
                end else begin
                    memory_child_d = 1'b0;
                    memory_write_d = 1'b0;
                    memory_base_d = ADDR_W'(CACHE_BASE) + (ADDR_W'(header_head_q) << 4);
                    memory_words_d = 3'd4;
                    memory_resume_d = ST_EVICT_HEADER;
                    state_d = ST_MEMORY_REQ;
                end
            end
            ST_EVICT_HEADER: begin
                row_d = row_head_q;
                count_d = buffer_q[79:64];
                index_d = '0;
                state_d = ST_EVICT_ROW;
                if (groups_q == '0 || buffer_q[63:32] != 32'(row_head_q) ||
                        buffer_q[95:64] == '0 || buffer_q[95:64] > 32'(rows_used_q) || buffer_q[127:96] != 32'd1) begin
                    error_d = 4'd4;
                    state_d = ST_RESULT;
                    poison_d = 1'b1;
                end
            end
            ST_EVICT_ROW: begin
                cam_op_d = CAM_INVALIDATE;
                cam_resume_d = ST_EVICT_NEXT;
                state_d = ST_CAM_REQ;
            end
            ST_EVICT_NEXT: begin
                row_d = (row_q == ROW_W'(CAM_ENTRIES-1)) ? '0 : row_q + ROW_W'(1);
                if (index_q + 16'd1 == count_q) begin
                    row_head_d = row_d;
                    rows_used_d = rows_used_q - ROW_COUNT_W'(count_q);
                    groups_d = groups_q - ROW_COUNT_W'(1);
                    header_head_d = (header_head_q == ROW_W'(CAM_ENTRIES-1)) ? '0 : header_head_q + ROW_W'(1);
                    state_d = ST_EVICT;
                end else begin
                    index_d = index_q + 16'd1;
                    state_d = ST_EVICT_ROW;
                end
            end
            ST_FILL: begin
                memory_child_d = 1'b1;
                memory_write_d = 1'b0;
                memory_base_d = (ADDR_W'(child_start_q) + ADDR_W'(index_q)) << 2;
                memory_words_d = 3'd1;
                memory_resume_d = ST_FILL_CHILD;
                state_d = ST_MEMORY_REQ;
            end
            ST_FILL_CHILD: begin
                cam_child_d = buffer_q[31:0];
                row_d = row_tail_q;
                cam_op_d = CAM_FILL;
                cam_resume_d = ST_FILL_ACK;
                state_d = ST_CAM_REQ;
                if (buffer_q[31:0] >= allocated_nodes_q) begin
                    error_d = 4'd1;
                    state_d = ST_RESULT;
                    poison_d = 1'b1;
                end
            end
            ST_FILL_ACK: begin
                row_tail_d = (row_tail_q == ROW_W'(CAM_ENTRIES-1)) ? '0 : row_tail_q + ROW_W'(1);
                rows_used_d = rows_used_q + ROW_COUNT_W'(1);
                if (index_q + 16'd1 == child_count_q) state_d = ST_HEADER_WRITE;
                else begin
                    index_d = index_q + 16'd1;
                    state_d = ST_FILL;
                end
            end
            ST_HEADER_WRITE: begin
                memory_child_d = 1'b0;
                memory_write_d = 1'b1;
                memory_base_d = ADDR_W'(CACHE_BASE) + (ADDR_W'(header_slot_q) << 4);
                memory_words_d = 3'd4;
                buffer_d[127:0] = {32'd1, 16'd0, child_count_q, 32'(first_row_q), node_q};
                memory_resume_d = ST_FLAGS_WRITE;
                state_d = ST_MEMORY_REQ;
            end
            ST_FLAGS_WRITE: begin
                memory_child_d = 1'b0;
                memory_write_d = 1'b1;
                memory_base_d = ADDR_W'(NODE_BASE+20) + ADDR_W'(node_q) * ADDR_W'(NODE_STRIDE);
                memory_words_d = 3'd1;
                buffer_d[31:0] = {header_slot_q[14:0], player_q, child_count_q};
                memory_resume_d = ST_REFILL_SEARCH;
                state_d = ST_MEMORY_REQ;
            end
            ST_REFILL_SEARCH: begin
                groups_d = groups_q + ROW_COUNT_W'(1);
                header_tail_d = (header_tail_q == ROW_W'(CAM_ENTRIES-1)) ? '0 : header_tail_q + ROW_W'(1);
                cam_op_d = CAM_SEARCH;
                cam_resume_d = ST_READ_HEADER;
                state_d = ST_CAM_REQ;
            end
            ST_READ_HEADER: begin
                memory_child_d = 1'b0;
                memory_write_d = 1'b0;
                memory_base_d = ADDR_W'(CACHE_BASE) + (ADDR_W'(header_slot_q) << 4);
                memory_words_d = 3'd4;
                memory_resume_d = ST_CHECK_HEADER;
                state_d = ST_MEMORY_REQ;
                if (header_slot_q >= 16'(CAM_ENTRIES) || matches_q == '0) begin
                    error_d = 4'd4;
                    state_d = ST_RESULT;
                    poison_d = 1'b1;
                end
            end
            ST_CHECK_HEADER: begin
                row_d = ROW_W'(buffer_q[63:32]);
                index_d = '0;
                state_d = ST_COLLECT;
                if (buffer_q[31:0] != node_q || buffer_q[63:32] >= 32'(CAM_ENTRIES) ||
                        buffer_q[95:64] != {16'd0, child_count_q} || buffer_q[127:96] != 32'd1) begin
                    error_d = 4'd4;
                    state_d = ST_RESULT;
                    poison_d = 1'b1;
                end
            end
            ST_COLLECT: begin
                cam_op_d = CAM_READ;
                cam_resume_d = ST_COLLECT_DONE;
                state_d = ST_CAM_REQ;
                if (32'(row_q) >= 32'(CAM_ENTRIES) || !matches_q[row_q]) begin
                    error_d = 4'd4;
                    state_d = ST_RESULT;
                    poison_d = 1'b1;
                end
            end
            ST_COLLECT_DONE: begin
                if (32'(row_q) < 32'(CAM_ENTRIES)) matches_d[row_q] = 1'b0;
                row_d = (row_q == ROW_W'(CAM_ENTRIES-1)) ? '0 : row_q + ROW_W'(1);
                if (index_q < 16'(MAX_CHILDREN)) child_ids_d[CHILD_W'(index_q)] = cam_child_q;
                if (index_q + 16'd1 == child_count_q) begin
                    index_d = '0;
                    best_valid_d = 1'b0;
                    state_d = ST_CANDIDATE;
                end else begin
                    index_d = index_q + 16'd1;
                    state_d = ST_COLLECT;
                end
                if (!cam_valid_q || cam_parent_q != node_q || cam_child_q >= allocated_nodes_q ||
                        index_q >= 16'(MAX_CHILDREN) || (index_q + 16'd1 == child_count_q && matches_d != '0)) begin
                    error_d = 4'd4;
                    state_d = ST_RESULT;
                    poison_d = 1'b1;
                end
            end
            ST_CANDIDATE: begin
                candidate_d = '0;
                if (index_q < 16'(MAX_CHILDREN)) candidate_d = child_ids_q[CHILD_W'(index_q)];
                memory_child_d = 1'b0;
                memory_write_d = 1'b0;
                memory_base_d = ADDR_W'(NODE_BASE) + ADDR_W'(candidate_d) * ADDR_W'(NODE_STRIDE);
                memory_words_d = 3'd6;
                memory_resume_d = ST_STAGE;
                state_d = ST_MEMORY_REQ;
                if (index_q >= 16'(MAX_CHILDREN) || candidate_d >= allocated_nodes_q) begin
                    error_d = 4'd1;
                    state_d = ST_RESULT;
                    poison_d = 1'b1;
                end
            end
            ST_STAGE: begin
                memory_child_d = 1'b0;
                memory_write_d = 1'b1;
                memory_base_d = ADDR_W'(STATS_BASE);
                memory_words_d = 3'd4;
                buffer_d[127:0] = {buffer_q[95:0], candidate_q};
                memory_resume_d = ST_READ_STAGE;
                state_d = ST_MEMORY_REQ;
                if (buffer_q[127:96] != node_q || buffer_q[94:84] == 11'h7ff) begin
                    error_d = 4'd4;
                    state_d = ST_RESULT;
                    poison_d = 1'b1;
                end
            end
            ST_READ_STAGE: begin
                memory_child_d = 1'b0;
                memory_write_d = 1'b0;
                memory_base_d = ADDR_W'(STATS_BASE);
                memory_words_d = 3'd4;
                memory_resume_d = ST_SCORE;
                state_d = ST_MEMORY_REQ;
            end
            ST_SCORE: begin
                visits_d = buffer_q[63:32];
                value_d = buffer_q[127:64];
                state_d = ST_SCORE_REQ;
                if (buffer_q[63:32] == '0) begin
                    node_d = candidate_q;
                    state_d = ST_NODE_READ;
                end
                if (buffer_q[31:0] != candidate_q || buffer_q[126:116] == 11'h7ff) begin
                    error_d = 4'd4;
                    state_d = ST_RESULT;
                    poison_d = 1'b1;
                end
            end
            ST_SCORE_REQ: begin
                if (score_req_ready) state_d = ST_SCORE_WAIT;
            end
            ST_SCORE_WAIT: begin
                if (score_rsp_valid) begin
                    score_d = score_rsp_value;
                    state_d = ST_SCORE_DONE;
                    if (score_rsp_error || score_rsp_value[62:52] == 11'h7ff) begin
                        error_d = 4'd5;
                        state_d = ST_RESULT;
                        poison_d = 1'b1;
                    end
                end
            end
            ST_SCORE_DONE: begin
                if (better) begin
                    best_valid_d = 1'b1;
                    best_score_d = score_q;
                    best_child_d = candidate_q;
                end
                if (index_q + 16'd1 == child_count_q) begin
                    node_d = better ? candidate_q : best_child_q;
                    state_d = ST_NODE_READ;
                end else begin
                    index_d = index_q + 16'd1;
                    state_d = ST_CANDIDATE;
                end
            end
            ST_MEMORY_REQ: begin
                if (memory_ready) state_d = ST_MEMORY_WAIT;
            end
            ST_MEMORY_WAIT: begin
                if (memory_valid) begin
                    if (!memory_write_q && memory_index_q < 3'd6)
                        buffer_d[int'(memory_index_q)*32 +: 32] = memory_data;
                    if (memory_index_q + 3'd1 == memory_words_q) begin
                        memory_index_d = '0;
                        state_d = memory_resume_q;
                    end else begin
                        memory_index_d = memory_index_q + 3'd1;
                        state_d = ST_MEMORY_REQ;
                    end
                    if (memory_error) begin
                        error_d = 4'd2;
                        state_d = ST_RESULT;
                        poison_d = 1'b1;
                    end
                end
            end
            ST_CAM_REQ: begin
                if (cam_req_ready) state_d = ST_CAM_WAIT;
            end
            ST_CAM_WAIT: begin
                if (cam_rsp_valid) begin
                    if (cam_op_q == CAM_SEARCH) matches_d = cam_rsp_matches;
                    if (cam_op_q == CAM_READ) begin
                        cam_child_d = cam_rsp_child;
                        cam_parent_d = cam_rsp_parent;
                        cam_valid_d = cam_rsp_row_valid;
                    end
                    state_d = cam_resume_q;
                    if (cam_rsp_error) begin
                        error_d = 4'd3;
                        state_d = ST_RESULT;
                        poison_d = 1'b1;
                    end
                end
            end
            ST_RESULT: begin
                if (result_ready) state_d = ST_IDLE;
            end
            default: begin
                error_d = 4'd7;
                state_d = ST_RESULT;
                poison_d = 1'b1;
            end
        endcase
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q <= ST_IDLE;
            memory_resume_q <= ST_IDLE;
            cam_resume_q <= ST_IDLE;
            cam_op_q <= CAM_SEARCH;
            node_q <= '0;
            allocated_nodes_q <= '0;
            allocated_edges_q <= '0;
            path_limit_q <= '0;
            path_depth <= '0;
            parent_visits_q <= '0;
            child_start_q <= '0;
            child_count_q <= '0;
            header_slot_q <= '0;
            player_q <= 1'b0;
            poisoned <= 1'b0;
            result_error <= '0;
            exploration_q <= '0;
            row_head_q <= '0;
            row_tail_q <= '0;
            header_head_q <= '0;
            header_tail_q <= '0;
            rows_used_q <= '0;
            groups_q <= '0;
            row_q <= '0;
            first_row_q <= '0;
            count_q <= '0;
            index_q <= '0;
            matches_q <= '0;
            for (j = 0; j < MAX_CHILDREN; j = j + 1) child_ids_q[j] <= '0;
            candidate_q <= '0;
            visits_q <= '0;
            value_q <= '0;
            score_q <= '0;
            best_score_q <= '0;
            best_child_q <= '0;
            best_valid_q <= 1'b0;
            memory_child_q <= 1'b0;
            memory_write_q <= 1'b0;
            memory_base_q <= '0;
            memory_words_q <= '0;
            memory_index_q <= '0;
            buffer_q <= '0;
            cam_child_q <= '0;
            cam_parent_q <= '0;
            cam_valid_q <= 1'b0;
        end else begin
            state_q <= state_d;
            memory_resume_q <= memory_resume_d;
            cam_resume_q <= cam_resume_d;
            cam_op_q <= cam_op_d;
            node_q <= node_d;
            allocated_nodes_q <= allocated_nodes_d;
            allocated_edges_q <= allocated_edges_d;
            path_limit_q <= path_limit_d;
            path_depth <= depth_d;
            parent_visits_q <= parent_visits_d;
            child_start_q <= child_start_d;
            child_count_q <= child_count_d;
            header_slot_q <= header_slot_d;
            player_q <= player_d;
            poisoned <= poison_d;
            result_error <= error_d;
            exploration_q <= exploration_d;
            row_head_q <= row_head_d;
            row_tail_q <= row_tail_d;
            header_head_q <= header_head_d;
            header_tail_q <= header_tail_d;
            rows_used_q <= rows_used_d;
            groups_q <= groups_d;
            row_q <= row_d;
            first_row_q <= first_row_d;
            count_q <= count_d;
            index_q <= index_d;
            matches_q <= matches_d;
            for (j = 0; j < MAX_CHILDREN; j = j + 1) child_ids_q[j] <= child_ids_d[j];
            candidate_q <= candidate_d;
            visits_q <= visits_d;
            value_q <= value_d;
            score_q <= score_d;
            best_score_q <= best_score_d;
            best_child_q <= best_child_d;
            best_valid_q <= best_valid_d;
            memory_child_q <= memory_child_d;
            memory_write_q <= memory_write_d;
            memory_base_q <= memory_base_d;
            memory_words_q <= memory_words_d;
            memory_index_q <= memory_index_d;
            buffer_q <= buffer_d;
            cam_child_q <= cam_child_d;
            cam_parent_q <= cam_parent_d;
            cam_valid_q <= cam_valid_d;
        end
    end
endmodule

`default_nettype wire
