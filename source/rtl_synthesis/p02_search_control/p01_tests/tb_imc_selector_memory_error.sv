// Check SRAM error responses at the selector's logical word boundary.
// Both ports propagate faults, poison the cache and recover after coordinated reset.
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_selector_memory_error;
    localparam int BOARD_SIZE=2, CAM_ENTRIES=7, ADDR_W=21, ROW_W=3, ROW_COUNT_W=3;
    logic clk = '0;
    logic rst_n = '0;
    logic start = '0;
    logic ready;
    logic [31:0] root_id = '0;
    logic [31:0] nodes_used = '0;
    logic [31:0] edges_used = '0;
    logic [31:0] path_limit = '0;
    logic [63:0] exploration_constant = '0;
    logic result_valid;
    logic result_ready = '0;
    logic [31:0] leaf_id;
    logic [31:0] path_depth;
    logic [3:0] result_error;
    logic poisoned;
    logic node_req_valid;
    logic node_req_ready = '0;
    logic node_req_write;
    logic [ADDR_W-1:0] node_req_addr;
    logic [31:0] node_req_wdata;
    logic node_rsp_valid = '0;
    logic node_rsp_ready;
    logic [31:0] node_rsp_rdata = '0;
    logic node_rsp_error = '0;
    logic child_req_valid;
    logic child_req_ready = '0;
    logic [ADDR_W-1:0] child_req_addr;
    logic child_rsp_valid = '0;
    logic child_rsp_ready;
    logic [31:0] child_rsp_rdata = '0;
    logic child_rsp_error = '0;
    logic cam_req_valid;
    logic cam_req_ready = '0;
    logic [1:0] cam_req_op;
    logic [ROW_W-1:0] cam_req_row;
    logic [31:0] cam_req_parent;
    logic [31:0] cam_req_child;
    logic cam_rsp_valid = '0;
    logic cam_rsp_ready;
    logic cam_rsp_error = '0;
    logic [CAM_ENTRIES-1:0] cam_rsp_matches = '0;
    logic [31:0] cam_rsp_parent = '0;
    logic [31:0] cam_rsp_child = '0;
    logic cam_rsp_row_valid = '0;
    logic score_req_valid;
    logic score_req_ready = '0;
    logic [31:0] score_parent_visits;
    logic [31:0] score_child_visits;
    logic [63:0] score_child_value;
    logic [63:0] score_exploration;
    logic score_rsp_valid = '0;
    logic score_rsp_ready;
    logic [63:0] score_rsp_value = '0;
    logic score_rsp_error = '0;
    logic [5:0] debug_state;
    logic [ROW_COUNT_W-1:0] cache_rows_used;
    logic [ROW_W-1:0] cache_row_head;
    logic [ROW_W-1:0] cache_row_tail;

    imc_cached_selector #(.BOARD_SIZE(2),.CAM_ENTRIES(7),.NEURAL_BYTES(16424)) dut (.*);
    always #5 clk=~clk;
    integer mode=0, requests=0, saved_requests=0, word_index=0;
    logic fired=0;
    task automatic tick;
        @(posedge clk); #1;
    endtask
    task automatic begin_request;
        @(negedge clk);
        root_id=0; nodes_used=2; edges_used=1; path_limit=5;
        exploration_constant=64'h3ff0000000000000;
        start=1;
        tick();
        @(negedge clk); start=0;
    endtask
    task automatic release_result;
        saved_requests=requests;
        repeat (4) begin
            tick();
            if (!result_valid || requests!=saved_requests) $fatal(1,"held result issued more work");
        end
        @(negedge clk); result_ready=1;
        tick();
        @(negedge clk); result_ready=0;
    endtask
    always @(posedge clk) begin
        if (!rst_n) begin
            node_rsp_valid<=0; child_rsp_valid<=0; cam_rsp_valid<=0;
            node_rsp_error<=0; child_rsp_error<=0;
            fired<=0;
        end else begin
            if (node_rsp_valid && node_rsp_ready) node_rsp_valid<=0;
            if (child_rsp_valid && child_rsp_ready) child_rsp_valid<=0;
            if (cam_rsp_valid && cam_rsp_ready) cam_rsp_valid<=0;
            if (node_req_valid && node_req_ready) begin
                requests=requests+1;
                node_rsp_valid<=1;
                node_rsp_error<=!fired && ((mode==0 && !node_req_write) || (mode==1 && node_req_write));
                if (!fired && ((mode==0 && !node_req_write) || (mode==1 && node_req_write))) fired<=1;
                node_rsp_rdata<=0;
                if (node_req_addr>=16576 && node_req_addr<16600) begin
                    word_index=(int'(node_req_addr)-16576)/4;
                    case(word_index)
                        0: node_rsp_rdata<=mode==3 ? 0 : 100;
                        3: node_rsp_rdata<=32'hffffffff;
                        5: node_rsp_rdata<=1;
                        default: node_rsp_rdata<=0;
                    endcase
                end
            end
            if (child_req_valid && child_req_ready) begin
                requests=requests+1;
                child_rsp_valid<=1;
                child_rsp_error<=mode==2;
                child_rsp_rdata<=1;
                fired<=mode==2;
            end
            if (cam_req_valid && cam_req_ready) begin
                requests=requests+1;
                if (cam_req_op!=0) $fatal(1,"memory error failed to stop cache fill");
                cam_rsp_valid<=1;
                cam_rsp_matches<=0;
            end
            if (score_req_valid) $fatal(1,"unexpected score work");
        end
    end
    initial begin
        node_req_ready=1; child_req_ready=1; cam_req_ready=1;
        for(mode=0;mode<4;mode=mode+1) begin
            @(negedge clk); rst_n=0;
            tick(); tick();
            if (poisoned || cache_rows_used || result_valid) $fatal(1,"reset failed");
            @(negedge clk); rst_n=1;
            begin_request();
            while (!result_valid) tick();
            if(mode<3) begin
                if(result_error!=2 || !poisoned || !fired) $fatal(1,"SRAM error did not propagate for mode %0d",mode);
                release_result();
                saved_requests=requests;
                begin_request();
                if(!result_valid || result_error!=8 || requests!=saved_requests) $fatal(1,"poisoned request issued work");
                release_result();
            end else begin
                if(result_error || poisoned || leaf_id!=0 || path_depth!=1) $fatal(1,"selection did not recover after reset");
                release_result();
            end
        end
        $display("tb_imc_selector_memory_error PASS read/write/child faults and reset recovery");
        $finish;
    end
    initial begin #100000; $fatal(1,"watchdog expired"); end
endmodule
