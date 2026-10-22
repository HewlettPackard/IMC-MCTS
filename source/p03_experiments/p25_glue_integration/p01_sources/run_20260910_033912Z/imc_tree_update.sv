// Expand immutable placement child lists or backpropagate a mapped Q17 value.
// Packed SRAM is authoritative; allocation is preflighted before child writes.
// Expansion appends one chosen child to the path; backprop consumes leaf to root.
// Hold completion until accepted. Runtime failures poison until coordinated reset.
// PPA role: packed_expansion_and_backpropagation
// SPDX-License-Identifier: MIT
`default_nettype none
module imc_tree_update #(
    parameter int BOARD_SIZE = 9,
    parameter int CAM_ENTRIES = 1024,
    parameter int NEURAL_BYTES = 16512,
    parameter int ADDR_W = 21,
    parameter int NODE_BYTES = 1572864,
    parameter int CHILD_BYTES = 524288
) (
    input  logic                  clk,
    input  logic                  rst_n,
    input  logic                  start,
    output logic                  ready,
    input  logic                  backpropagate,
    input  logic [31:0]           selected_node,
    input  logic [31:0]           nodes_used,
    input  logic [31:0]           edges_used,
    input  logic [31:0]           selected_depth,
    input  logic [31:0]           node_limit,
    input  logic [31:0]           edge_limit,
    input  logic [31:0]           path_limit,
    input  logic [31:0]           choice_word,
    input  logic [31:0]           value_q17,
    output logic                  result_valid,
    input  logic                  result_ready,
    output logic [31:0]           result_node,
    output logic [31:0]           result_nodes_used,
    output logic [31:0]           result_edges_used,
    output logic [31:0]           result_depth,
    output logic [31:0]           nodes_changed,
    output logic [3:0]            result_error,
    output logic                  poisoned,
    output logic                  node_req_valid,
    input  logic                  node_req_ready,
    output logic                  node_req_write,
    output logic [ADDR_W-1:0]      node_req_addr,
    output logic [31:0]           node_req_wdata,
    input  logic                  node_rsp_valid,
    output logic                  node_rsp_ready,
    input  logic [31:0]           node_rsp_rdata,
    input  logic                  node_rsp_error,
    output logic                  child_req_valid,
    input  logic                  child_req_ready,
    output logic                  child_req_write,
    output logic [ADDR_W-1:0]      child_req_addr,
    output logic [31:0]           child_req_wdata,
    input  logic                  child_rsp_valid,
    output logic                  child_rsp_ready,
    input  logic [31:0]           child_rsp_rdata,
    input  logic                  child_rsp_error,
    output logic [5:0]            debug_state
);
    localparam int POSITIONS = BOARD_SIZE * BOARD_SIZE;
    localparam int BOARD_WORDS = (2 * POSITIONS + 31) / 32;
    localparam int WORDS = 6 + BOARD_WORDS;
    localparam int WORD_W = $clog2(WORDS + 1);
    localparam int INDEX_W = (POSITIONS < 2) ? 1 : $clog2(POSITIONS);
    localparam int WORKING = 4 * (POSITIONS + 1);
    localparam int NODE_BASE = WORKING + 4 * BOARD_WORDS + 16 + 16 * CAM_ENTRIES + NEURAL_BYTES;
    localparam int NODE_STRIDE = 4 * WORDS;
    localparam int NODE_CAPACITY = (NODE_BYTES - NODE_BASE) / NODE_STRIDE;
    localparam logic CONFIG_OK = POSITIONS > 0 && POSITIONS <= 32768 &&
        CAM_ENTRIES >= POSITIONS && CAM_ENTRIES <= 32768 && NODE_CAPACITY > 0 &&
        NODE_BYTES <= (2**ADDR_W) && CHILD_BYTES <= (2**ADDR_W);

    typedef enum logic [5:0] {
        ST_IDLE, ST_EXPAND_READ, ST_EXPAND_CHECK, ST_BOARD_READ,
        ST_WORK_WRITE, ST_WORK_READ, ST_COUNT, ST_CHILD_READ, ST_CHILD_BUILD,
        ST_CHILD_DONE, ST_EDGES, ST_EDGE_DONE, ST_ATTACH, ST_PUSH,
        ST_EXPAND_DONE, ST_POP, ST_POP_DONE, ST_STATS, ST_UPDATE,
        ST_UPDATED, ST_MEMORY_REQ, ST_MEMORY_WAIT, ST_RESULT
    } state_e;
    state_e state_q, state_d, resume_q, resume_d;
    logic [31:0] node_q, node_d, first_child_q, first_child_d, first_edge_q, first_edge_d;
    logic [31:0] node_limit_q, node_limit_d, edge_limit_q, edge_limit_d, path_limit_q, path_limit_d;
    logic [31:0] choice_q, choice_d, value_q, value_d, selected_q, selected_d;
    logic [31:0] result_nodes_d, result_edges_d, result_depth_d, changed_d;
    logic [15:0] count_q, count_d, child_q, child_d, empty_count;
    logic [POSITIONS-1:0] empty_q, empty_d, empty_mask;
    logic [INDEX_W-1:0] position;
    logic position_found, invalid_board, player_q, player_d;
    logic [3:0] error_d;
    logic poison_d, memory_child_q, memory_child_d, memory_write_q, memory_write_d;
    logic [ADDR_W-1:0] memory_base_q, memory_base_d;
    logic [WORD_W-1:0] memory_words_q, memory_words_d, memory_index_q, memory_index_d;
    logic [WORDS*32-1:0] buffer_q, buffer_d;
    logic memory_ready, memory_valid, memory_error;
    logic [31:0] memory_data;
    logic [48:0] old_value, new_value;
    logic [49:0] value_sum;
    logic codec_error;
    logic [63:0] new_binary;
    integer i;

    imc_q17_codec u_codec (
        .binary_value(buffer_q[95:32]),
        .decoded_value(old_value),
        .decode_error(codec_error),
        .encoded_value(new_value),
        .binary_result(new_binary)
    );

    assign ready = rst_n && state_q == ST_IDLE;
    assign result_valid = rst_n && state_q == ST_RESULT;
    assign result_node = selected_q;
    assign debug_state = state_q;
    assign node_req_valid = rst_n && state_q == ST_MEMORY_REQ && !memory_child_q;
    assign child_req_valid = rst_n && state_q == ST_MEMORY_REQ && memory_child_q;
    assign node_req_write = memory_write_q;
    assign child_req_write = memory_write_q;
    assign node_req_addr = memory_base_q + (ADDR_W'(memory_index_q) << 2);
    assign child_req_addr = node_req_addr;
    assign node_req_wdata = memory_index_q < WORD_W'(WORDS) ? buffer_q[int'(memory_index_q)*32 +: 32] : 32'd0;
    assign child_req_wdata = node_req_wdata;
    assign node_rsp_ready = rst_n && state_q == ST_MEMORY_WAIT && !memory_child_q;
    assign child_rsp_ready = rst_n && state_q == ST_MEMORY_WAIT && memory_child_q;
    assign memory_ready = memory_child_q ? child_req_ready : node_req_ready;
    assign memory_valid = memory_child_q ? child_rsp_valid : node_rsp_valid;
    assign memory_error = memory_child_q ? child_rsp_error : node_rsp_error;
    assign memory_data = memory_child_q ? child_rsp_rdata : node_rsp_rdata;
    assign value_sum = {1'b0, old_value} + (buffer_q[176] ? 50'd131072 - {18'd0, value_q} : {18'd0, value_q});
    assign new_value = value_sum[48:0];

    always_comb begin
        state_d = state_q;
        resume_d = resume_q;
        node_d = node_q;
        first_child_d = first_child_q;
        first_edge_d = first_edge_q;
        node_limit_d = node_limit_q;
        edge_limit_d = edge_limit_q;
        path_limit_d = path_limit_q;
        choice_d = choice_q;
        value_d = value_q;
        selected_d = selected_q;
        result_nodes_d = result_nodes_used;
        result_edges_d = result_edges_used;
        result_depth_d = result_depth;
        changed_d = nodes_changed;
        count_d = count_q;
        child_d = child_q;
        empty_d = empty_q;
        player_d = player_q;
        error_d = result_error;
        poison_d = poisoned;
        memory_child_d = memory_child_q;
        memory_write_d = memory_write_q;
        memory_base_d = memory_base_q;
        memory_words_d = memory_words_q;
        memory_index_d = memory_index_q;
        buffer_d = buffer_q;
        empty_mask = '0;
        empty_count = '0;
        invalid_board = 1'b0;
        position = '0;
        position_found = 1'b0;
        for (i = 0; i < POSITIONS; i = i + 1) begin
            empty_mask[i] = buffer_q[i*2 +: 2] == 2'd0;
            empty_count = empty_count + {15'd0, empty_mask[i]};
            if (buffer_q[i*2 +: 2] == 2'd3) invalid_board = 1'b1;
            if (empty_q[i] && !position_found) begin
                position = INDEX_W'(i);
                position_found = 1'b1;
            end
        end

        unique case (state_q)
            ST_IDLE: begin
                if (start) begin
                    node_d = selected_node;
                    selected_d = selected_node;
                    first_child_d = nodes_used;
                    first_edge_d = edges_used;
                    result_nodes_d = nodes_used;
                    result_edges_d = edges_used;
                    result_depth_d = selected_depth;
                    node_limit_d = node_limit;
                    edge_limit_d = edge_limit;
                    path_limit_d = path_limit;
                    choice_d = choice_word;
                    value_d = value_q17;
                    changed_d = '0;
                    error_d = '0;
                    if (backpropagate) state_d = ST_POP;
                    else state_d = ST_EXPAND_READ;
                    if (poisoned) begin
                        state_d = ST_RESULT;
                        error_d = 4'd8;
                    end else if (!CONFIG_OK || nodes_used == '0 || selected_node >= nodes_used || nodes_used > node_limit ||
                        node_limit > 32'(NODE_CAPACITY) || node_limit == '0 || edge_limit > 32'(CHILD_BYTES/4) ||
                        edges_used > edge_limit || selected_depth == '0 || selected_depth > path_limit ||
                        path_limit > 32'(POSITIONS+1) || (backpropagate && value_q17 > 32'd131072)) begin
                        state_d = ST_RESULT;
                        error_d = 4'd1;
                    end
                end
            end
            ST_EXPAND_READ: begin
                memory_child_d = 1'b0;
                memory_write_d = 1'b0;
                memory_base_d = ADDR_W'(NODE_BASE) + ADDR_W'(node_q) * ADDR_W'(NODE_STRIDE);
                memory_words_d = WORD_W'(6);
                resume_d = ST_EXPAND_CHECK;
                state_d = ST_MEMORY_REQ;
            end
            ST_EXPAND_CHECK: begin
                player_d = buffer_q[176];
                state_d = ST_BOARD_READ;
                if (buffer_q[31:0] == '0 || buffer_q[175:160] != '0) state_d = ST_RESULT;
            end
            ST_BOARD_READ: begin
                memory_child_d = 1'b0;
                memory_write_d = 1'b0;
                memory_base_d = ADDR_W'(NODE_BASE+24) + ADDR_W'(node_q) * ADDR_W'(NODE_STRIDE);
                memory_words_d = WORD_W'(BOARD_WORDS);
                resume_d = ST_WORK_WRITE;
                state_d = ST_MEMORY_REQ;
            end
            ST_WORK_WRITE: begin
                memory_write_d = 1'b1;
                memory_base_d = ADDR_W'(WORKING);
                resume_d = ST_WORK_READ;
                state_d = ST_MEMORY_REQ;
            end
            ST_WORK_READ: begin
                memory_write_d = 1'b0;
                resume_d = ST_COUNT;
                state_d = ST_MEMORY_REQ;
            end
            ST_COUNT: begin
                empty_d = empty_mask;
                count_d = empty_count;
                child_d = '0;
                state_d = ST_CHILD_READ;
                if (empty_count != '0) selected_d = first_child_q + choice_q % {16'd0, empty_count};
                if (invalid_board) begin
                    state_d = ST_RESULT;
                    error_d = 4'd4;
                    poison_d = 1'b1;
                end else if (empty_count == '0) state_d = ST_RESULT;
                else if ({1'b0, first_child_q}+{17'd0, empty_count} > {1'b0, node_limit_q} ||
                    {1'b0, first_edge_q}+{17'd0, empty_count} > {1'b0, edge_limit_q} || result_depth >= path_limit_q) begin
                    state_d = ST_RESULT;
                    error_d = 4'd3;
                    poison_d = 1'b1;
                end
            end
            ST_CHILD_READ: begin
                memory_child_d = 1'b0;
                memory_write_d = 1'b0;
                memory_base_d = ADDR_W'(WORKING);
                memory_words_d = WORD_W'(BOARD_WORDS);
                resume_d = ST_CHILD_BUILD;
                state_d = ST_MEMORY_REQ;
            end
            ST_CHILD_BUILD: begin
                buffer_d = buffer_q << 192;
                buffer_d[191:0] = {15'd0, !player_q, 16'd0, 32'hffffffff, node_q, 96'd0};
                if (32'(position) < 32'(POSITIONS)) buffer_d[192+int'(position)*2 +: 2] = player_q ? 2'd2 : 2'd1;
                if (32'(position) < 32'(POSITIONS)) empty_d[position] = 1'b0;
                memory_write_d = 1'b1;
                memory_base_d = ADDR_W'(NODE_BASE) + ADDR_W'(result_nodes_used) * ADDR_W'(NODE_STRIDE);
                memory_words_d = WORD_W'(WORDS);
                resume_d = ST_CHILD_DONE;
                state_d = ST_MEMORY_REQ;
                if (!position_found || invalid_board) begin
                    state_d = ST_RESULT;
                    error_d = 4'd4;
                    poison_d = 1'b1;
                end
            end
            ST_CHILD_DONE: begin
                result_nodes_d = result_nodes_used + 32'd1;
                changed_d = nodes_changed + 32'd1;
                if (child_q + 16'd1 == count_q) begin
                    child_d = '0;
                    state_d = ST_EDGES;
                end else begin
                    child_d = child_q + 16'd1;
                    state_d = ST_CHILD_READ;
                end
            end
            ST_EDGES: begin
                memory_child_d = 1'b1;
                memory_write_d = 1'b1;
                memory_base_d = ADDR_W'(result_edges_used) << 2;
                memory_words_d = WORD_W'(1);
                buffer_d[31:0] = first_child_q + {16'd0, child_q};
                resume_d = ST_EDGE_DONE;
                state_d = ST_MEMORY_REQ;
            end
            ST_EDGE_DONE: begin
                result_edges_d = result_edges_used + 32'd1;
                if (child_q + 16'd1 == count_q) state_d = ST_ATTACH;
                else begin
                    child_d = child_q + 16'd1;
                    state_d = ST_EDGES;
                end
            end
            ST_ATTACH: begin
                memory_child_d = 1'b0;
                memory_write_d = 1'b1;
                memory_base_d = ADDR_W'(NODE_BASE+16) + ADDR_W'(node_q) * ADDR_W'(NODE_STRIDE);
                memory_words_d = WORD_W'(2);
                buffer_d[63:0] = {15'd0, player_q, count_q, first_edge_q};
                resume_d = ST_PUSH;
                state_d = ST_MEMORY_REQ;
            end
            ST_PUSH: begin
                memory_base_d = ADDR_W'(result_depth) << 2;
                memory_words_d = WORD_W'(1);
                buffer_d[31:0] = selected_q;
                resume_d = ST_EXPAND_DONE;
                state_d = ST_MEMORY_REQ;
            end
            ST_EXPAND_DONE: begin
                result_depth_d = result_depth + 32'd1;
                state_d = ST_RESULT;
            end
            ST_POP: begin
                memory_child_d = 1'b0;
                memory_write_d = 1'b0;
                memory_base_d = ADDR_W'(result_depth-32'd1) << 2;
                memory_words_d = WORD_W'(1);
                resume_d = ST_POP_DONE;
                state_d = ST_MEMORY_REQ;
            end
            ST_POP_DONE: begin
                node_d = buffer_q[31:0];
                state_d = ST_STATS;
                if (buffer_q[31:0] >= result_nodes_used) begin
                    state_d = ST_RESULT;
                    error_d = 4'd4;
                    poison_d = 1'b1;
                end
            end
            ST_STATS: begin
                memory_base_d = ADDR_W'(NODE_BASE) + ADDR_W'(node_q) * ADDR_W'(NODE_STRIDE);
                memory_words_d = WORD_W'(6);
                resume_d = ST_UPDATE;
                state_d = ST_MEMORY_REQ;
            end
            ST_UPDATE: begin
                memory_write_d = 1'b1;
                memory_words_d = WORD_W'(3);
                buffer_d[95:0] = {new_binary, buffer_q[31:0]+32'd1};
                resume_d = ST_UPDATED;
                state_d = ST_MEMORY_REQ;
                if (codec_error || old_value > {buffer_q[31:0], 17'd0}) begin
                    state_d = ST_RESULT;
                    error_d = 4'd5;
                    poison_d = 1'b1;
                end else if (buffer_q[31:0] == 32'hffffffff || value_sum[49]) begin
                    state_d = ST_RESULT;
                    error_d = 4'd3;
                    poison_d = 1'b1;
                end
            end
            ST_UPDATED: begin
                result_depth_d = result_depth - 32'd1;
                changed_d = nodes_changed + 32'd1;
                if (result_depth == 32'd1) state_d = ST_RESULT;
                else state_d = ST_POP;
            end
            ST_MEMORY_REQ: if (memory_ready) state_d = ST_MEMORY_WAIT;
            ST_MEMORY_WAIT: begin
                if (memory_valid) begin
                    if (!memory_write_q && memory_index_q < WORD_W'(WORDS)) buffer_d[int'(memory_index_q)*32 +: 32] = memory_data;
                    if (memory_index_q + WORD_W'(1) == memory_words_q) begin
                        memory_index_d = '0;
                        state_d = resume_q;
                    end else begin
                        memory_index_d = memory_index_q + WORD_W'(1);
                        state_d = ST_MEMORY_REQ;
                    end
                    if (memory_error) begin
                        state_d = ST_RESULT;
                        error_d = 4'd2;
                        poison_d = 1'b1;
                    end
                end
            end
            ST_RESULT: if (result_ready) state_d = ST_IDLE;
            default: begin
                state_d = ST_RESULT;
                error_d = 4'd7;
                poison_d = 1'b1;
            end
        endcase
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q <= ST_IDLE;
            resume_q <= ST_IDLE;
            node_q <= '0;
            first_child_q <= '0;
            first_edge_q <= '0;
            node_limit_q <= '0;
            edge_limit_q <= '0;
            path_limit_q <= '0;
            choice_q <= '0;
            value_q <= '0;
            selected_q <= '0;
            result_nodes_used <= '0;
            result_edges_used <= '0;
            result_depth <= '0;
            nodes_changed <= '0;
            count_q <= '0;
            child_q <= '0;
            empty_q <= '0;
            player_q <= 1'b0;
            result_error <= '0;
            poisoned <= 1'b0;
            memory_child_q <= 1'b0;
            memory_write_q <= 1'b0;
            memory_base_q <= '0;
            memory_words_q <= '0;
            memory_index_q <= '0;
            buffer_q <= '0;
        end else begin
            state_q <= state_d;
            resume_q <= resume_d;
            node_q <= node_d;
            first_child_q <= first_child_d;
            first_edge_q <= first_edge_d;
            node_limit_q <= node_limit_d;
            edge_limit_q <= edge_limit_d;
            path_limit_q <= path_limit_d;
            choice_q <= choice_d;
            value_q <= value_d;
            selected_q <= selected_d;
            result_nodes_used <= result_nodes_d;
            result_edges_used <= result_edges_d;
            result_depth <= result_depth_d;
            nodes_changed <= changed_d;
            count_q <= count_d;
            child_q <= child_d;
            empty_q <= empty_d;
            player_q <= player_d;
            result_error <= error_d;
            poisoned <= poison_d;
            memory_child_q <= memory_child_d;
            memory_write_q <= memory_write_d;
            memory_base_q <= memory_base_d;
            memory_words_q <= memory_words_d;
            memory_index_q <= memory_index_d;
            buffer_q <= buffer_d;
        end
    end
endmodule
`default_nettype wire
