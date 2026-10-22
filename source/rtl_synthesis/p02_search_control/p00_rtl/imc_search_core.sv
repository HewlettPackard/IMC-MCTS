// Serialize cached selection and neural inference through one node SRAM router.
// Selection wins simultaneous starts; ownership lasts through accepted completion.
// SRAM/CAM/ADC/score responders reset together; no inter-operation overlap is assumed.
// PPA role: selection_and_neural_control_with_node_and_child_routers
// SPDX-License-Identifier: MIT
`default_nettype none
module imc_search_core #(
    parameter int BOARD_SIZE = 9,
    parameter int CAM_ENTRIES = 1024,
    parameter int HIDDEN = 96,
    parameter int ADDR_W = 21,
    parameter int ROW_W = (CAM_ENTRIES < 2) ? 1 : $clog2(CAM_ENTRIES),
    parameter int ROW_COUNT_W = $clog2(CAM_ENTRIES + 1)
) (
    input  logic                          clk,
    input  logic                          rst_n,
    input  logic                          select_start,
    output logic                          select_ready,
    input  logic [31:0]                   root_id,
    input  logic [31:0]                   nodes_used,
    input  logic [31:0]                   edges_used,
    input  logic [31:0]                   path_limit,
    input  logic [63:0]                   exploration_constant,
    output logic                          select_valid,
    input  logic                          select_result_ready,
    output logic [31:0]                   leaf_id,
    output logic [31:0]                   path_depth,
    output logic [3:0]                    select_error,
    output logic                          selection_poisoned,
    output logic                          cam_req_valid,
    input  logic                          cam_req_ready,
    output logic [1:0]                    cam_req_op,
    output logic [ROW_W-1:0]              cam_req_row,
    output logic [31:0]                   cam_req_parent,
    output logic [31:0]                   cam_req_child,
    input  logic                          cam_rsp_valid,
    output logic                          cam_rsp_ready,
    input  logic                          cam_rsp_error,
    input  logic [CAM_ENTRIES-1:0]        cam_rsp_matches,
    input  logic [31:0]                   cam_rsp_parent,
    input  logic [31:0]                   cam_rsp_child,
    input  logic                          cam_rsp_row_valid,
    output logic                          score_req_valid,
    input  logic                          score_req_ready,
    output logic [31:0]                   score_parent_visits,
    output logic [31:0]                   score_child_visits,
    output logic [63:0]                   score_child_value,
    output logic [63:0]                   score_exploration,
    input  logic                          score_rsp_valid,
    output logic                          score_rsp_ready,
    input  logic [63:0]                   score_rsp_value,
    input  logic                          score_rsp_error,
    output logic [5:0]                    selection_state,
    output logic [ROW_COUNT_W-1:0]        cache_rows_used,
    output logic [ROW_W-1:0]              cache_row_head,
    output logic [ROW_W-1:0]              cache_row_tail,
    input  logic                          neural_start,
    output logic                          neural_ready,
    input  logic [ADDR_W-1:0]             board_base,
    input  logic [5:0]                    hidden_shift,
    input  logic signed [7:0]             logit_shift,
    output logic                          neural_valid,
    input  logic                          neural_result_ready,
    output logic [31:0]                   value_code,
    output logic [3:0]                    neural_error,
    output logic                          drive_valid,
    input  logic                          drive_ready,
    output logic                          array_enable,
    output logic [3:0]                    array_id,
    output logic [7:0]                    row_start,
    output logic [4:0]                    row_count,
    output logic [15:0]                   row_bits,
    output logic [2:0]                    input_bit,
    output logic [7:0]                    column_start,
    output logic [1:0]                    column_count,
    output logic                          mux_select,
    output logic                          sample_hold,
    output logic                          adc_req_valid,
    input  logic                          adc_req_ready,
    input  logic                          adc_rsp_valid,
    output logic                          adc_rsp_ready,
    input  logic                          adc_rsp_error,
    input  logic [23:0]                   adc_rsp_codes,
    output logic                          hidden_saturated,
    output logic                          logit_saturated,
    output logic [5:0]                    neural_state,
    output logic [2:0]                    node_bank_valid,
    input  logic [2:0]                    node_bank_ready,
    output logic [2:0]                    node_bank_write,
    output logic [50:0]                   node_bank_addr,
    output logic [95:0]                   node_bank_wdata,
    input  logic [2:0]                    node_bank_rsp_valid,
    input  logic [95:0]                   node_bank_rdata,
    output logic                          child_bank_valid,
    input  logic                          child_bank_ready,
    output logic                          child_bank_write,
    output logic [16:0]                   child_bank_addr,
    output logic [31:0]                   child_bank_wdata,
    input  logic                          child_bank_rsp_valid,
    input  logic [31:0]                   child_bank_rdata,
    output logic [1:0]                    debug_owner
);

    localparam int BOARD_BYTES = 4 * ((2 * BOARD_SIZE * BOARD_SIZE + 31) / 32);
    localparam int NEURAL_BASE = 4 * (BOARD_SIZE * BOARD_SIZE + 1) + BOARD_BYTES + 16 + 16 * CAM_ENTRIES;
    localparam int NEURAL_BYTES = 4 * ((HIDDEN + 3) / 4) + 16416;
    typedef enum logic [1:0] { ST_IDLE, ST_SELECT, ST_NEURAL } owner_e;
    owner_e owner_q, owner_d;
    logic select_internal_ready, neural_internal_ready;
    logic router_req_valid, router_req_ready, router_req_write;
    logic [ADDR_W-1:0] router_req_addr;
    logic [31:0] router_req_wdata, router_rsp_rdata;
    logic router_rsp_valid, router_rsp_ready, router_rsp_error;
    logic sel_node_req_valid;
    logic sel_node_req_ready;
    logic sel_node_req_write;
    logic [ADDR_W-1:0] sel_node_req_addr;
    logic [31:0] sel_node_req_wdata;
    logic sel_node_rsp_valid;
    logic sel_node_rsp_ready;
    logic [31:0] sel_node_rsp_rdata;
    logic sel_node_rsp_error;
    logic sel_child_req_valid;
    logic sel_child_req_ready;
    logic [ADDR_W-1:0] sel_child_req_addr;
    logic sel_child_rsp_valid;
    logic sel_child_rsp_ready;
    logic [31:0] sel_child_rsp_rdata;
    logic sel_child_rsp_error;
    logic nn_mem_req_valid;
    logic nn_mem_req_ready;
    logic [ADDR_W-1:0] nn_mem_req_addr;
    logic nn_mem_req_write;
    logic [31:0] nn_mem_req_wdata;
    logic nn_mem_rsp_valid;
    logic nn_mem_rsp_ready;
    logic nn_mem_rsp_error;
    logic [31:0] nn_mem_rsp_rdata;

    assign select_ready = rst_n && owner_q == ST_IDLE && select_internal_ready;
    assign neural_ready = rst_n && owner_q == ST_IDLE && !select_start && neural_internal_ready;
    assign debug_owner = owner_q;
    assign router_req_valid = (owner_q == ST_SELECT) ? sel_node_req_valid :
        (owner_q == ST_NEURAL) ? nn_mem_req_valid : 1'b0;
    assign router_req_write = (owner_q == ST_SELECT) ? sel_node_req_write : nn_mem_req_write;
    assign router_req_addr = (owner_q == ST_SELECT) ? sel_node_req_addr : nn_mem_req_addr;
    assign router_req_wdata = (owner_q == ST_SELECT) ? sel_node_req_wdata : nn_mem_req_wdata;
    assign router_rsp_ready = (owner_q == ST_SELECT) ? sel_node_rsp_ready :
        (owner_q == ST_NEURAL) ? nn_mem_rsp_ready : 1'b0;
    assign sel_node_req_ready = owner_q == ST_SELECT && router_req_ready;
    assign nn_mem_req_ready = owner_q == ST_NEURAL && router_req_ready;
    assign sel_node_rsp_valid = owner_q == ST_SELECT && router_rsp_valid;
    assign nn_mem_rsp_valid = owner_q == ST_NEURAL && router_rsp_valid;
    assign sel_node_rsp_rdata = router_rsp_rdata;
    assign nn_mem_rsp_rdata = router_rsp_rdata;
    assign sel_node_rsp_error = router_rsp_error;
    assign nn_mem_rsp_error = router_rsp_error;

    always_comb begin
        owner_d = owner_q;
        unique case (owner_q)
            ST_IDLE: begin
                if (select_start && select_ready) owner_d = ST_SELECT;
                else if (neural_start && neural_ready) owner_d = ST_NEURAL;
            end
            ST_SELECT: if (select_valid && select_result_ready) owner_d = ST_IDLE;
            ST_NEURAL: if (neural_valid && neural_result_ready) owner_d = ST_IDLE;
            default: owner_d = ST_IDLE;
        endcase
    end

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) owner_q <= ST_IDLE;
        else owner_q <= owner_d;
    end

    imc_cached_selector #(.BOARD_SIZE(BOARD_SIZE), .CAM_ENTRIES(CAM_ENTRIES), .NEURAL_BYTES(NEURAL_BYTES), .ADDR_W(ADDR_W)) u_selector (
        .clk(clk),
        .rst_n(rst_n),
        .start(select_start && select_ready),
        .ready(select_internal_ready),
        .root_id(root_id),
        .nodes_used(nodes_used),
        .edges_used(edges_used),
        .path_limit(path_limit),
        .exploration_constant(exploration_constant),
        .result_valid(select_valid),
        .result_ready(select_result_ready),
        .leaf_id(leaf_id),
        .path_depth(path_depth),
        .result_error(select_error),
        .poisoned(selection_poisoned),
        .node_req_valid(sel_node_req_valid),
        .node_req_ready(sel_node_req_ready),
        .node_req_write(sel_node_req_write),
        .node_req_addr(sel_node_req_addr),
        .node_req_wdata(sel_node_req_wdata),
        .node_rsp_valid(sel_node_rsp_valid),
        .node_rsp_ready(sel_node_rsp_ready),
        .node_rsp_rdata(sel_node_rsp_rdata),
        .node_rsp_error(sel_node_rsp_error),
        .child_req_valid(sel_child_req_valid),
        .child_req_ready(sel_child_req_ready),
        .child_req_addr(sel_child_req_addr),
        .child_rsp_valid(sel_child_rsp_valid),
        .child_rsp_ready(sel_child_rsp_ready),
        .child_rsp_rdata(sel_child_rsp_rdata),
        .child_rsp_error(sel_child_rsp_error),
        .cam_req_valid(cam_req_valid),
        .cam_req_ready(cam_req_ready),
        .cam_req_op(cam_req_op),
        .cam_req_row(cam_req_row),
        .cam_req_parent(cam_req_parent),
        .cam_req_child(cam_req_child),
        .cam_rsp_valid(cam_rsp_valid),
        .cam_rsp_ready(cam_rsp_ready),
        .cam_rsp_error(cam_rsp_error),
        .cam_rsp_matches(cam_rsp_matches),
        .cam_rsp_parent(cam_rsp_parent),
        .cam_rsp_child(cam_rsp_child),
        .cam_rsp_row_valid(cam_rsp_row_valid),
        .score_req_valid(score_req_valid),
        .score_req_ready(score_req_ready),
        .score_parent_visits(score_parent_visits),
        .score_child_visits(score_child_visits),
        .score_child_value(score_child_value),
        .score_exploration(score_exploration),
        .score_rsp_valid(score_rsp_valid),
        .score_rsp_ready(score_rsp_ready),
        .score_rsp_value(score_rsp_value),
        .score_rsp_error(score_rsp_error),
        .debug_state(selection_state),
        .cache_rows_used(cache_rows_used),
        .cache_row_head(cache_row_head),
        .cache_row_tail(cache_row_tail)
    );
    imc_neural_sequencer #(.INPUTS(2 * BOARD_SIZE * BOARD_SIZE), .HIDDEN(HIDDEN), .ADDR_W(ADDR_W)) u_neural (
        .clk(clk),
        .rst_n(rst_n),
        .start(neural_start && neural_ready),
        .ready(neural_internal_ready),
        .board_base(board_base),
        .neural_base(ADDR_W'(NEURAL_BASE)),
        .hidden_shift(hidden_shift),
        .logit_shift(logit_shift),
        .result_valid(neural_valid),
        .result_ready(neural_result_ready),
        .value_code(value_code),
        .result_error(neural_error),
        .mem_req_valid(nn_mem_req_valid),
        .mem_req_ready(nn_mem_req_ready),
        .mem_req_addr(nn_mem_req_addr),
        .mem_req_write(nn_mem_req_write),
        .mem_req_wdata(nn_mem_req_wdata),
        .mem_rsp_valid(nn_mem_rsp_valid),
        .mem_rsp_ready(nn_mem_rsp_ready),
        .mem_rsp_error(nn_mem_rsp_error),
        .mem_rsp_rdata(nn_mem_rsp_rdata),
        .drive_valid(drive_valid),
        .drive_ready(drive_ready),
        .array_enable(array_enable),
        .array_id(array_id),
        .row_start(row_start),
        .row_count(row_count),
        .row_bits(row_bits),
        .input_bit(input_bit),
        .column_start(column_start),
        .column_count(column_count),
        .mux_select(mux_select),
        .sample_hold(sample_hold),
        .adc_req_valid(adc_req_valid),
        .adc_req_ready(adc_req_ready),
        .adc_rsp_valid(adc_rsp_valid),
        .adc_rsp_ready(adc_rsp_ready),
        .adc_rsp_error(adc_rsp_error),
        .adc_rsp_codes(adc_rsp_codes),
        .hidden_saturated(hidden_saturated),
        .logit_saturated(logit_saturated),
        .debug_state(neural_state)
    );
    imc_sram_router #(.BANKS(3), .BANK_BYTE_W(19), .ADDR_W(ADDR_W)) u_node_router (
        .clk(clk),
        .rst_n(rst_n),
        .req_valid(router_req_valid),
        .req_ready(router_req_ready),
        .req_addr(router_req_addr),
        .req_write(router_req_write),
        .req_wdata(router_req_wdata),
        .rsp_valid(router_rsp_valid),
        .rsp_ready(router_rsp_ready),
        .rsp_error(router_rsp_error),
        .rsp_rdata(router_rsp_rdata),
        .bank_valid(node_bank_valid),
        .bank_ready(node_bank_ready),
        .bank_write(node_bank_write),
        .bank_addr(node_bank_addr),
        .bank_wdata(node_bank_wdata),
        .bank_rsp_valid(node_bank_rsp_valid),
        .bank_rdata(node_bank_rdata)
    );
    imc_sram_router #(.BANKS(1), .BANK_BYTE_W(19), .ADDR_W(ADDR_W)) u_child_router (
        .clk(clk),
        .rst_n(rst_n),
        .req_valid(sel_child_req_valid),
        .req_ready(sel_child_req_ready),
        .req_addr(sel_child_req_addr),
        .req_write(1'b0),
        .req_wdata(32'd0),
        .rsp_valid(sel_child_rsp_valid),
        .rsp_ready(sel_child_rsp_ready),
        .rsp_error(sel_child_rsp_error),
        .rsp_rdata(sel_child_rsp_rdata),
        .bank_valid(child_bank_valid),
        .bank_ready(child_bank_ready),
        .bank_write(child_bank_write),
        .bank_addr(child_bank_addr),
        .bank_wdata(child_bank_wdata),
        .bank_rsp_valid(child_bank_rsp_valid),
        .bank_rdata(child_bank_rdata)
    );
endmodule
`default_nettype wire
