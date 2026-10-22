// Exercise real SRAM routers, CAM commands and score/ADC interfaces.
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_search_core #(
    parameter int BOARD_SIZE = 2,
    parameter int CAM_ENTRIES = 7,
    parameter int HIDDEN = 5,
    parameter int CASES = 12,
    parameter int TRANSACTIONS = 1310,
    parameter int PATCHES = 168,
    parameter int PATH_WORDS = 34,
    parameter int ADC_GROUPS = 39,
    parameter int NEURAL_WORDS = 20,
    parameter int RESULT_WORDS = 9,
    parameter int STALL = 0,
    parameter int FAULT = 0,
    parameter int ADDR_W = 21,
    parameter int ROW_W = $clog2(CAM_ENTRIES),
    parameter int ROW_COUNT_W = $clog2(CAM_ENTRIES+1)
);
    logic clk = '0;
    logic rst_n = '0;
    logic select_start = '0;
    logic select_ready;
    logic [31:0] root_id = '0;
    logic [31:0] nodes_used = '0;
    logic [31:0] edges_used = '0;
    logic [31:0] path_limit = '0;
    logic [63:0] exploration_constant = '0;
    logic select_valid;
    logic select_result_ready = '0;
    logic [31:0] leaf_id;
    logic [31:0] path_depth;
    logic [3:0] select_error;
    logic selection_poisoned;
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
    logic [5:0] selection_state;
    logic [ROW_COUNT_W-1:0] cache_rows_used;
    logic [ROW_W-1:0] cache_row_head;
    logic [ROW_W-1:0] cache_row_tail;
    logic neural_start = '0;
    logic neural_ready;
    logic [ADDR_W-1:0] board_base = '0;
    logic [5:0] hidden_shift = '0;
    logic signed [7:0] logit_shift = '0;
    logic neural_valid;
    logic neural_result_ready = '0;
    logic [31:0] value_code;
    logic [3:0] neural_error;
    logic drive_valid;
    logic drive_ready = '0;
    logic array_enable;
    logic [3:0] array_id;
    logic [7:0] row_start;
    logic [4:0] row_count;
    logic [15:0] row_bits;
    logic [2:0] input_bit;
    logic [7:0] column_start;
    logic [1:0] column_count;
    logic mux_select;
    logic sample_hold;
    logic adc_req_valid;
    logic adc_req_ready = '0;
    logic adc_rsp_valid = '0;
    logic adc_rsp_ready;
    logic adc_rsp_error = '0;
    logic [23:0] adc_rsp_codes = '0;
    logic hidden_saturated;
    logic logit_saturated;
    logic [5:0] neural_state;
    logic [2:0] node_bank_valid;
    logic [2:0] node_bank_ready = '0;
    logic [2:0] node_bank_write;
    logic [50:0] node_bank_addr;
    logic [95:0] node_bank_wdata;
    logic [2:0] node_bank_rsp_valid = '0;
    logic [95:0] node_bank_rdata = '0;
    logic child_bank_valid;
    logic child_bank_ready = '0;
    logic child_bank_write;
    logic [16:0] child_bank_addr;
    logic [31:0] child_bank_wdata;
    logic child_bank_rsp_valid = '0;
    logic [31:0] child_bank_rdata = '0;
    logic [1:0] debug_owner;

`ifdef IMC_POST_SYNTH
    imc_search_core dut (.*);
`else
    imc_search_core #(.BOARD_SIZE(BOARD_SIZE), .CAM_ENTRIES(CAM_ENTRIES), .HIDDEN(HIDDEN)) dut (.*);
`endif
    always #5 clk = ~clk;

    localparam int BOARD_BYTES = 4*((2*BOARD_SIZE*BOARD_SIZE+31)/32);
    localparam int NEURAL_BASE = 4*(BOARD_SIZE*BOARD_SIZE+1)+BOARD_BYTES+16+16*CAM_ENTRIES;
    logic [31:0] node_memory [0:393215];
    logic [31:0] child_memory [0:131071];
    logic [31:0] keys [0:CAM_ENTRIES-1];
    logic [31:0] values [0:CAM_ENTRIES-1];
    logic [CAM_ENTRIES-1:0] valid_rows = '0;
    logic [CAM_ENTRIES-1:0] found;
    logic [511:0] cases [0:CASES-1];
    logic [319:0] transactions [0:TRANSACTIONS-1];
    logic [319:0] neural_transactions [0:NEURAL_WORDS-1];
    logic [63:0] patches [0:PATCHES-1];
    logic [31:0] paths [0:PATH_WORDS-1];
    logic [71:0] adc_vectors [0:ADC_GROUPS-1];
    logic [31:0] neural_results [0:RESULT_WORDS-1];
    logic [71:0] adc_expected;
    logic [319:0] expected;
    logic [511:0] descriptor;
    logic [2:0] node_pending = '0;
    logic child_pending = 0, cam_pending = 0, score_pending = 0, adc_pending = 0;
    logic [95:0] node_pending_data;
    logic [31:0] child_pending_data;
    integer node_delay [0:2];
    integer child_delay = 0, cam_delay = 0, score_delay = 0, adc_delay = 0;
    integer cycle = 0, case_index = 0, transaction_index = 0, neural_index = 0, adc_index = 0;
    integer events, word_address, address, start_cycle, neural_after, expected_value;
    integer i, j, bank, patch_index, case_start, adc_requests, drive_count, mux_count, sample_count;
    integer completed_cases = 0, reset_epochs = 0;
    logic neural_running = 0, fault_fired = 0, reset_probe = 0;
    string fixture_path, events_path;

    task automatic tick;
        @(posedge clk); #1;
    endtask

    task automatic check_transaction(input integer target, input integer op,
        input logic [31:0] addr, input logic [31:0] data,
        input logic [31:0] child, input logic [63:0] value, input logic [63:0] constant_bits);
        begin
            $fdisplay(events,"request,%0d,%0d,%0d,%0d,%0d,%0d,%08x",reset_epochs,case_index,cycle,target,op,addr,data);
            if (!fault_fired) begin
                if (neural_running) begin
                    if (neural_index >= NEURAL_WORDS) $fatal(1,"extra neural SRAM transfer");
                    expected = neural_transactions[neural_index];
                    neural_index = neural_index+1;
                end else begin
                    if (transaction_index >= TRANSACTIONS) $fatal(1,"extra selection transfer");
                    expected = transactions[transaction_index];
                    transaction_index = transaction_index+1;
                end
                if ({target[3:0],op[3:0],addr,data} !== expected[319:248])
                    $fatal(1,"transaction %0d differs: actual target/op/addr/data=%0d/%0d/%0d/%h expected=%h",transaction_index-1,target,op,addr,data,expected[319:248]);
                if (target == 2 && (op == 1 || op == 3) && child !== expected[247:216])
                    $fatal(1,"CAM child ID differs");
                if (target == 3 && {child,value,constant_bits} !== expected[247:88])
                    $fatal(1,"score request differs");
            end
        end
    endtask

    always @(negedge clk) begin
        for (bank=0;bank<3;bank=bank+1)
            node_bank_ready[bank] = rst_n && !node_pending[bank] && (!STALL || ((cycle+bank)%5 != 0));
        child_bank_ready = rst_n && !child_pending && (!STALL || cycle%5 != 0);
        cam_req_ready = rst_n && !cam_pending && !cam_rsp_valid && (!STALL || cycle%3 != 0);
        score_req_ready = rst_n && !score_pending && !score_rsp_valid && (!STALL || cycle%4 != 0);
        drive_ready = rst_n && (!STALL || cycle%4 != 0);
        adc_req_ready = rst_n && !adc_pending && !adc_rsp_valid && (!STALL || cycle%3 != 0);
    end

    always @(posedge clk) begin
        cycle = cycle+1;
        if (!rst_n) begin
            node_bank_rsp_valid <= '0;
            child_bank_rsp_valid <= 1'b0;
            node_pending <= '0;
            child_pending <= 1'b0;
            cam_pending <= 1'b0;
            score_pending <= 1'b0;
            adc_pending <= 1'b0;
            cam_rsp_valid <= 1'b0;
            score_rsp_valid <= 1'b0;
            adc_rsp_valid <= 1'b0;
            cam_rsp_error <= 1'b0;
            score_rsp_error <= 1'b0;
            adc_rsp_error <= 1'b0;
            valid_rows <= '0;
            for (j=0;j<CAM_ENTRIES;j=j+1) begin keys[j] <= '0; values[j] <= '0; end
        end else begin
            if ((cam_req_valid || score_req_valid || child_bank_valid) && debug_owner != 2'd1)
                $fatal(1,"selection issued without SRAM ownership");
            if ((drive_valid || adc_req_valid) && debug_owner != 2'd2)
                $fatal(1,"neural issued without SRAM ownership");
            if (debug_owner != '0 && (select_ready || neural_ready)) $fatal(1,"busy owner accepted another operation");
            node_bank_rsp_valid <= '0;
            child_bank_rsp_valid <= 1'b0;
            for (j=0;j<3;j=j+1) begin
                if (node_pending[j]) begin
                    if (node_delay[j] == 0) begin
                        node_bank_rsp_valid[j] <= 1'b1;
                        node_bank_rdata[j*32 +: 32] <= node_pending_data[j*32 +: 32];
                        node_pending[j] <= 1'b0;
                    end else node_delay[j] <= node_delay[j]-1;
                end
                if (node_bank_valid[j] && node_bank_ready[j]) begin
                    word_address = j*131072+int'(node_bank_addr[j*17 +: 17]);
                    check_transaction(0,int'(node_bank_write[j]),32'(word_address*4),
                        node_bank_write[j] ? node_bank_wdata[j*32 +: 32] : node_memory[word_address],0,0,0);
                    if (node_bank_write[j]) node_memory[word_address] <= node_bank_wdata[j*32 +: 32];
                    if (STALL) begin
                        node_pending[j] <= 1'b1;
                        node_delay[j] <= (cycle+j)%3;
                        node_pending_data[j*32 +: 32] <= node_memory[word_address];
                    end else begin
                        node_bank_rsp_valid[j] <= 1'b1;
                        node_bank_rdata[j*32 +: 32] <= node_memory[word_address];
                    end
                end
            end
            if (child_pending) begin
                if (child_delay == 0) begin
                    child_bank_rsp_valid <= 1'b1;
                    child_bank_rdata <= child_pending_data;
                    child_pending <= 1'b0;
                end else child_delay <= child_delay-1;
            end
            if (child_bank_valid && child_bank_ready) begin
                if (child_bank_write) $fatal(1,"selector wrote child SRAM");
                check_transaction(1,0,32'(child_bank_addr)*4,child_memory[child_bank_addr],0,0,0);
                if (STALL) begin
                    child_pending <= 1'b1;
                    child_delay <= cycle%3;
                    child_pending_data <= child_memory[child_bank_addr];
                end else begin
                    child_bank_rsp_valid <= 1'b1;
                    child_bank_rdata <= child_memory[child_bank_addr];
                end
            end
            if (cam_rsp_valid && cam_rsp_ready) cam_rsp_valid <= 1'b0;
            if (cam_pending) begin
                if (cam_delay == 1) begin cam_rsp_valid <= 1'b1; cam_pending <= 1'b0; end
                else cam_delay <= cam_delay-1;
            end
            if (cam_req_valid && cam_req_ready) begin
                if (int'(cam_req_row) >= CAM_ENTRIES && cam_req_op != 2'd0) $fatal(1,"CAM row exceeds capacity");
                if (cam_req_op == 2'd0) begin
                    check_transaction(2,0,cam_req_parent,0,0,0,0);
                    found = '0;
                    for (j=0;j<CAM_ENTRIES;j=j+1)
                        if (valid_rows[j] && keys[j] == cam_req_parent) found[j] = 1'b1;
                    cam_rsp_matches <= found;
                end else if (cam_req_op == 2'd1) begin
                    check_transaction(2,1,32'(cam_req_row),cam_req_parent,cam_req_child,0,0);
                    keys[cam_req_row] <= cam_req_parent;
                    values[cam_req_row] <= cam_req_child;
                    valid_rows[cam_req_row] <= 1'b1;
                end else if (cam_req_op == 2'd2) begin
                    check_transaction(2,2,32'(cam_req_row),0,0,0,0);
                    valid_rows[cam_req_row] <= 1'b0;
                end else begin
                    check_transaction(2,3,32'(cam_req_row),keys[cam_req_row],values[cam_req_row],0,0);
                    cam_rsp_parent <= keys[cam_req_row];
                    cam_rsp_child <= values[cam_req_row];
                    cam_rsp_row_valid <= valid_rows[cam_req_row];
                end
                cam_pending <= 1'b1;
                cam_delay <= 1+(STALL ? cycle%3 : 0);
                cam_rsp_error <= 1'b0;
                if (FAULT == 1 && !fault_fired) begin cam_rsp_error <= 1'b1; fault_fired = 1; end
                if (FAULT == 4 && !fault_fired && cam_req_op == 2'd3) begin
                    cam_rsp_parent <= 32'hffffffff;
                    fault_fired = 1;
                end
            end
            if (score_rsp_valid && score_rsp_ready) score_rsp_valid <= 1'b0;
            if (score_pending) begin
                if (score_delay == 1) begin score_rsp_valid <= 1'b1; score_pending <= 1'b0; end
                else score_delay <= score_delay-1;
            end
            if (score_req_valid && score_req_ready) begin
                check_transaction(3,0,0,score_parent_visits,score_child_visits,score_child_value,score_exploration);
                score_rsp_value <= expected[87:24];
                score_pending <= 1'b1;
                score_delay <= 2+(STALL ? cycle%4 : 0);
                score_rsp_error <= 1'b0;
                if (FAULT == 2 && !fault_fired) begin score_rsp_error <= 1'b1; fault_fired = 1; end
                if (FAULT == 3 && !fault_fired) begin score_rsp_value <= 64'h7ff8000000000001; fault_fired = 1; end
            end
            if (adc_rsp_valid && adc_rsp_ready) adc_rsp_valid <= 1'b0;
            if (adc_pending) begin
                if (adc_delay == 1) begin adc_rsp_valid <= 1'b1; adc_pending <= 1'b0; end
                else adc_delay <= adc_delay-1;
            end
            if (drive_valid && drive_ready) drive_count = drive_count+1;
            if (mux_select) mux_count = mux_count+1;
            if (sample_hold) sample_count = sample_count+1;
            if (adc_req_valid && adc_req_ready) begin
                if (!neural_running || adc_index >= ADC_GROUPS) $fatal(1,"unexpected ADC request");
                adc_expected = adc_vectors[adc_index];
                if ({array_id,row_start,row_count,input_bit,row_bits,column_start,column_count,2'b00} !== adc_expected[71:24])
                    $fatal(1,"ADC metadata differs at group %0d",adc_index);
                adc_rsp_codes <= adc_expected[23:0];
                adc_pending <= 1'b1;
                adc_delay <= 8+(STALL ? adc_index%4 : 0);
                adc_index = adc_index+1;
                adc_rsp_error <= 1'b0;
                if (FAULT == 8 && !fault_fired) begin adc_rsp_error <= 1'b1; fault_fired = 1; end
            end
        end
    end

    task automatic prepare_selection(input integer index);
        begin
            @(negedge clk);
            case_index = index;
            descriptor = cases[index];
            transaction_index = int'(descriptor[31:0]);
            for (patch_index=int'(descriptor[95:64]);patch_index<int'(descriptor[95:64]+descriptor[127:96]);patch_index=patch_index+1)
                node_memory[patches[patch_index][63:32]/4] = patches[patch_index][31:0];
            root_id = descriptor[319:288];
            nodes_used = descriptor[351:320];
            edges_used = descriptor[383:352];
            path_limit = (FAULT == 5) ? 32'd2 : descriptor[415:384];
            exploration_constant = descriptor[511:448];
            if (FAULT == 6) root_id = nodes_used;
            select_start = 1'b1;
            neural_start = (index == neural_after);
            #1;
            if (!select_ready || (neural_start && neural_ready)) $fatal(1,"start arbitration failed");
            tick();
            start_cycle = cycle;
            @(negedge clk);
            select_start = 1'b0;
            neural_start = 1'b0;
            root_id = '1;
            nodes_used = '0;
            edges_used = '0;
            path_limit = '0;
            exploration_constant = '1;
        end
    endtask

    task automatic release_selection;
        begin
            repeat (4) begin
                tick();
                if (!select_valid || select_ready || neural_ready || node_bank_valid != '0 || child_bank_valid || cam_req_valid || score_req_valid)
                    $fatal(1,"completion backpressure changed state or ownership");
            end
            @(negedge clk); select_result_ready = 1'b1;
            tick();
            @(negedge clk); select_result_ready = 1'b0;
        end
    endtask

    task automatic check_selection;
        begin
            while (!select_valid) tick();
            $fdisplay(events,"selection,%0d,%0d,%0d,%0d,%0d,%0d",reset_epochs,case_index,cycle-start_cycle,leaf_id,path_depth,select_error);
            if (select_error != 0) begin
                if ((FAULT == 1 && select_error != 3) || ((FAULT == 2 || FAULT == 3) && select_error != 5) ||
                    (FAULT == 4 && select_error != 4) || (FAULT == 5 && select_error != 6) ||
                    (FAULT == 6 && select_error != 1) || FAULT == 0 || FAULT >= 7)
                    $fatal(1,"unexpected selection error %0d in case %0d",select_error,case_index);
                if (selection_poisoned !== (FAULT != 6)) $fatal(1,"incorrect poison state");
                release_selection();
                if (FAULT != 6) begin
                    @(negedge clk); select_start = 1'b1;
                    tick();
                    @(negedge clk); select_start = 1'b0;
                    if (!select_valid || select_error != 8) $fatal(1,"poisoned selector did not require reset");
                    release_selection();
                end
                $display("tb_imc_search_core PASS fault=%0d",FAULT);
                $fclose(events); $finish;
            end
            if (leaf_id !== descriptor[159:128] || path_depth !== descriptor[191:160]) $fatal(1,"selected path differs");
            if (transaction_index != int'(descriptor[31:0]+descriptor[63:32])) $fatal(1,"selection traffic incomplete");
            if (32'(cache_rows_used) !== descriptor[223:192] || 32'(cache_row_head) !== descriptor[255:224] || 32'(cache_row_tail) !== descriptor[287:256])
                $fatal(1,"FIFO cache state differs");
            for (i=0;i<int'(path_depth);i=i+1)
                if (node_memory[i] !== paths[int'(descriptor[447:416])+i]) $fatal(1,"packed path SRAM differs");
            completed_cases = completed_cases+1;
            release_selection();
        end
    endtask

    task automatic run_neural;
        begin
            @(negedge clk);
            neural_running = 1;
            neural_index = 0; adc_index = 0;
            drive_count = 0; mux_count = 0; sample_count = 0;
            neural_start = 1;
            #1;
            if (!neural_ready) $fatal(1,"neural start not ready after selection");
            tick(); start_cycle = cycle;
            @(negedge clk); neural_start = 0;
            select_start = 1;
            tick();
            if (select_ready) $fatal(1,"selection entered during neural ownership");
            @(negedge clk); select_start = 0;
            while (!neural_valid) tick();
            $fdisplay(events,"neural,%0d,%0d,%0d,%0d,%0d",reset_epochs,case_index,cycle-start_cycle,value_code,neural_error);
            if (FAULT == 8) begin
                if (neural_error != 3 || !fault_fired) $fatal(1,"ADC error did not propagate");
            end else begin
                if (neural_error != 0 || value_code != 32'(expected_value)) $fatal(1,"neural value differs");
                if (neural_index != NEURAL_WORDS || adc_index != ADC_GROUPS || mux_count != ADC_GROUPS || sample_count != ADC_GROUPS)
                    $fatal(1,"neural operation counts differ");
                for (i=0;i<RESULT_WORDS;i=i+1)
                    if (node_memory[NEURAL_BASE/4+i] !== neural_results[i]) $fatal(1,"neural SRAM result differs");
                if (!STALL && cycle-start_cycle != (BOARD_SIZE == 9 ? 26620 : 891)) $fatal(1,"neural timing changed through shared router");
            end
            repeat (4) begin tick(); if (!neural_valid || select_ready || neural_ready) $fatal(1,"neural completion lost ownership"); end
            @(negedge clk); neural_result_ready = 1;
            tick();
            @(negedge clk); neural_result_ready = 0;
            neural_running = 0;
            fault_fired = 0;
        end
    endtask

    initial begin
        if (!$value$plusargs("FIXTURE=%s",fixture_path)) $fatal(1,"FIXTURE missing");
        if (!$value$plusargs("EVENTS=%s",events_path)) $fatal(1,"EVENTS missing");
        if (!$value$plusargs("NEURAL_AFTER=%d",neural_after)) $fatal(1,"NEURAL_AFTER missing");
        if (!$value$plusargs("BOARD_BASE=%d",board_base)) $fatal(1,"BOARD_BASE missing");
        if (!$value$plusargs("HIDDEN_SHIFT=%d",hidden_shift)) $fatal(1,"HIDDEN_SHIFT missing");
        if (!$value$plusargs("LOGIT_SHIFT=%d",logit_shift)) $fatal(1,"LOGIT_SHIFT missing");
        if (!$value$plusargs("EXPECTED_VALUE=%d",expected_value)) $fatal(1,"EXPECTED_VALUE missing");
        events = $fopen(events_path,"w");
        if (!events) $fatal(1,"cannot open event log");
        for (i=0;i<393216;i=i+1) node_memory[i] = '0;
        for (i=0;i<131072;i=i+1) child_memory[i] = '0;
        $readmemh({fixture_path,"/node.hex"},node_memory);
        $readmemh({fixture_path,"/child.hex"},child_memory);
        $readmemh({fixture_path,"/cases.hex"},cases);
        $readmemh({fixture_path,"/transactions.hex"},transactions);
        $readmemh({fixture_path,"/neural_transactions.hex"},neural_transactions);
        $readmemh({fixture_path,"/patches.hex"},patches);
        $readmemh({fixture_path,"/paths.hex"},paths);
        $readmemh({fixture_path,"/neural/adc.hex"},adc_vectors);
        $readmemh({fixture_path,"/neural/expected.hex"},neural_results);
        tick(); tick();
        @(negedge clk); rst_n = 1;
        if (FAULT == 7) begin
            prepare_selection(0); check_selection();
            prepare_selection(1);
            wait(cam_req_valid && cam_req_ready);
            tick();
            @(negedge clk); rst_n = 0; select_start = 0; neural_start = 0;
            tick(); tick();
            if (debug_owner != '0 || select_valid || neural_valid || cache_rows_used != '0) $fatal(1,"reset did not clear ownership/cache state");
            @(negedge clk); rst_n = 1;
            reset_epochs = 1;
            transaction_index = 0;
        end
        for (case_start=0;case_start<CASES;case_start=case_start+1) begin
            prepare_selection(case_start);
            check_selection();
            if (case_start == neural_after) run_neural();
        end
        if (FAULT > 0 && FAULT < 7) $fatal(1,"requested fault was not reached");
        $display("tb_imc_search_core PASS cases=%0d stall=%0d fault=%0d",completed_cases,STALL,FAULT);
        $fclose(events); $finish;
    end
endmodule
