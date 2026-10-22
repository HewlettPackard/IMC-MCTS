// Full jobs with ideal SRAM/CAM/ADC responders and arbitrary service stalls.
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_buffered_iteration_core #(
    parameter int BOARD_SIZE=2, CAM_ENTRIES=7, HIDDEN=5,
    parameter int ADDR_W=21, STALL=0, FAULT=0, CHECK_CYCLES=1,
    parameter int ROW_W=$clog2(CAM_ENTRIES), ROW_COUNT_W=$clog2(CAM_ENTRIES+1)
);
    logic clk = '0;
    logic rst_n = '0;
    logic start = '0;
    logic ready;
    logic [31:0] root_id = '0;
    logic [31:0] initial_nodes = '0;
    logic [31:0] initial_edges = '0;
    logic [31:0] iteration_limit = '0;
    logic [31:0] node_limit = '0;
    logic [31:0] edge_limit = '0;
    logic [31:0] path_limit = '0;
    logic [31:0] seed = '0;
    logic [63:0] exploration_constant = '0;
    logic [5:0] hidden_shift = '0;
    logic signed [7:0] logit_shift = '0;
    logic result_valid;
    logic result_ready = '0;
    logic [7:0] result_error;
    logic iteration_done;
    logic [63:0] cycle_count;
    logic [31:0] iterations_completed;
    logic [31:0] allocated_nodes;
    logic [31:0] allocated_edges;
    logic [31:0] selected_node;
    logic [31:0] current_depth;
    logic [31:0] last_value;
    logic [31:0] random_state;
    logic [3:0] debug_phase;
    logic [1:0] debug_owner;
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
    logic [5:0] sel_state;
    logic [ROW_COUNT_W-1:0] cache_rows_used;
    logic [ROW_W-1:0] cache_row_head;
    logic [ROW_W-1:0] cache_row_tail;
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
    logic [5:0] nn_state;
    logic [5:0] upd_state;
    logic [3:0] ucb_state;
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

`ifdef IMC_POST_SYNTH
    imc_buffered_iteration_core dut (.*);
`else
    imc_buffered_iteration_core #(.BOARD_SIZE(BOARD_SIZE),.CAM_ENTRIES(CAM_ENTRIES),.HIDDEN(HIDDEN)) dut (.*);
`endif
    always #5 clk=~clk;
    logic [31:0] node_memory [0:393215], child_memory [0:131071];
    logic [31:0] expected_node [0:393215], expected_child [0:131071];
    logic [319:0] transactions [0:199999], expected, actual;
    logic [255:0] iterations [0:255];
    logic [71:0] adc_vectors [0:299999], adc_vector;
    logic [CAM_ENTRIES-1:0] valid_rows='0, found;
    logic [31:0] keys [0:CAM_ENTRIES-1], values [0:CAM_ENTRIES-1];
    logic [2:0] node_pending='0;
    logic child_pending=0, cam_pending=0, adc_pending=0, fault_fired=0;
    logic [95:0] node_pending_data;
    logic [31:0] child_pending_data;
    integer node_delay [0:2];
    integer child_delay=0, cam_delay=0, adc_delay=0;
    integer cycle=0, transaction_index=0, adc_index=0, iteration_index=0;
    integer i,j,word_address,count,adc_count,iteration_count,events,hidden_setting,logit_setting;
    integer nodes_cap,edges_cap,path_cap,previous_phase=-1,saved_requests;
    string directory,event_path;
    task automatic tick;
        @(posedge clk); #1;
    endtask
    task automatic check_transfer(input integer target, input integer op, input logic [31:0] address,
                                 input logic [31:0] data, input logic [31:0] child);
        begin
            actual={4'(target),4'(op),address,data,child,216'd0};
            if(!fault_fired) begin
                if(transaction_index>=count) $fatal(1,"extra transfer %0d",transaction_index);
                expected=transactions[transaction_index];
                if(actual!==expected) $fatal(1,"transfer %0d actual=%h expected=%h phase=%0d",transaction_index,actual,expected,debug_phase);
            end
            $fdisplay(events,"transfer,%0d,%0d,%0d,%0d,%0d,%08x,%0d",iterations_completed,cycle_count,target,op,address,data,child);
            transaction_index=transaction_index+1;
        end
    endtask
    wire signed [31:0] HOLD_ADC_LIMIT = adc_count;
    wire signed [31:0] hold_run = int'(iterations_completed);
    `include "p01_tests/held_columns.svh"
    always @(negedge clk) begin
        for(i=0;i<3;i=i+1) node_bank_ready[i]=rst_n && !node_pending[i] && (!STALL || (cycle+i)%5!=0);
        child_bank_ready=rst_n && !child_pending && (!STALL || cycle%5!=0);
        cam_req_ready=rst_n && !cam_pending && !cam_rsp_valid && (!STALL || cycle%3!=0);
        drive_ready=rst_n && (!STALL || cycle%4!=0);
        adc_req_ready=rst_n && !adc_pending && !adc_rsp_valid && (!STALL || cycle%3!=0);
    end
    always @(posedge clk) begin
        cycle=cycle+1;
        if(!rst_n) begin
            node_bank_rsp_valid<='0; child_bank_rsp_valid<=0; node_pending<='0; child_pending<=0;
            cam_pending<=0; cam_rsp_valid<=0; cam_rsp_error<=0; valid_rows<='0;
            adc_pending<=0; adc_rsp_valid<=0; adc_rsp_error<=0;
        end else begin
            if(int'(debug_phase)!=previous_phase) begin
                $fdisplay(events,"phase,%0d,%0d,%0d",iterations_completed,cycle_count,debug_phase);
                previous_phase=int'(debug_phase);
            end
            node_bank_rsp_valid<='0; child_bank_rsp_valid<=0;
            for(j=0;j<3;j=j+1) begin
                if(node_pending[j]) begin
                    if(node_delay[j]==0) begin
                        node_bank_rsp_valid[j]<=1; node_bank_rdata[j*32+:32]<=node_pending_data[j*32+:32]; node_pending[j]<=0;
                    end else node_delay[j]<=node_delay[j]-1;
                end
                if(node_bank_valid[j] && node_bank_ready[j]) begin
                    word_address=j*131072+int'(node_bank_addr[j*17+:17]);
                    check_transfer(0,int'(node_bank_write[j]),32'(word_address*4),
                        node_bank_write[j] ? node_bank_wdata[j*32+:32] : node_memory[word_address],0);
                    if(node_bank_write[j]) node_memory[word_address]<=node_bank_wdata[j*32+:32];
                    if(STALL) begin node_pending[j]<=1; node_delay[j]<=(cycle+j)%3; node_pending_data[j*32+:32]<=node_memory[word_address]; end
                    else begin node_bank_rsp_valid[j]<=1; node_bank_rdata[j*32+:32]<=node_memory[word_address]; end
                end
            end
            if(child_pending) begin
                if(child_delay==0) begin child_bank_rsp_valid<=1; child_bank_rdata<=child_pending_data; child_pending<=0; end
                else child_delay<=child_delay-1;
            end
            if(child_bank_valid && child_bank_ready) begin
                check_transfer(1,int'(child_bank_write),32'(child_bank_addr)*4,
                    child_bank_write ? child_bank_wdata : child_memory[child_bank_addr],0);
                if(child_bank_write) child_memory[child_bank_addr]<=child_bank_wdata;
                if(STALL) begin child_pending<=1; child_delay<=cycle%3; child_pending_data<=child_memory[child_bank_addr]; end
                else begin child_bank_rsp_valid<=1; child_bank_rdata<=child_memory[child_bank_addr]; end
            end
            if(cam_rsp_valid && cam_rsp_ready) cam_rsp_valid<=0;
            if(cam_pending) begin
                if(cam_delay==1) begin cam_rsp_valid<=1; cam_pending<=0; end
                else cam_delay<=cam_delay-1;
            end
            if(cam_req_valid && cam_req_ready) begin
                if(cam_req_op==0) begin
                    check_transfer(2,0,cam_req_parent,0,0); found='0;
                    for(j=0;j<CAM_ENTRIES;j=j+1) if(valid_rows[j] && keys[j]==cam_req_parent) found[j]=1;
                    cam_rsp_matches<=found;
                end else begin
                    if(int'(cam_req_row)>=CAM_ENTRIES) $fatal(1,"CAM address exceeds capacity");
                    case(cam_req_op)
                        1: begin
                            check_transfer(2,1,32'(cam_req_row),cam_req_parent,cam_req_child);
                            keys[cam_req_row]<=cam_req_parent; values[cam_req_row]<=cam_req_child; valid_rows[cam_req_row]<=1;
                        end
                        2: begin check_transfer(2,2,32'(cam_req_row),0,0); valid_rows[cam_req_row]<=0; end
                        3: begin
                            check_transfer(2,3,32'(cam_req_row),keys[cam_req_row],values[cam_req_row]);
                            cam_rsp_parent<=keys[cam_req_row]; cam_rsp_child<=values[cam_req_row]; cam_rsp_row_valid<=valid_rows[cam_req_row];
                        end
                    endcase
                end
                cam_rsp_error<=FAULT==1 && !fault_fired;
                if(FAULT==1 && !fault_fired) fault_fired=1;
                cam_pending<=1; cam_delay<=1+(STALL ? cycle%3 : 0);
            end
            if(adc_rsp_valid && adc_rsp_ready) adc_rsp_valid<=0;
            if(adc_pending) begin
                if(adc_delay==1) begin adc_rsp_valid<=1; adc_pending<=0; end
                else adc_delay<=adc_delay-1;
            end
            if(adc_req_valid && adc_req_ready) begin
                if(adc_index>=adc_count) $fatal(1,"extra ADC request");
                adc_vector=adc_vectors[adc_index];
                if({array_id,row_start,row_count,input_bit,row_bits,column_start,column_count}!==adc_vector[71:26])
                    $fatal(1,"ADC geometry/drive differs at %0d actual=%h expected=%h",adc_index,
                        {array_id,row_start,row_count,input_bit,row_bits,column_start,column_count},adc_vector[71:26]);
                adc_rsp_codes<=sampled_codes; adc_index=adc_index+1;
                adc_rsp_error<=FAULT==2 && !fault_fired;
                if(FAULT==2 && !fault_fired) fault_fired=1;
                adc_pending<=1; adc_delay<=8+(STALL ? cycle%4 : 0);
            end
        end
    end
    always @(posedge clk) begin
        #2;
        if(rst_n && iteration_done) begin
            if(iteration_index>=iteration_count) $fatal(1,"extra completed iteration");
            if({random_state,last_value,allocated_edges,allocated_nodes,selected_node,iterations_completed}!==iterations[iteration_index][191:0])
                $fatal(1,"iteration state differs at %0d actual=%h expected=%h",iteration_index,
                    {random_state,last_value,allocated_edges,allocated_nodes,selected_node,iterations_completed},iterations[iteration_index][191:0]);
            $fdisplay(events,"iteration,%0d,%0d,%0d,%0d,%0d,%0d",iterations_completed,cycle_count,selected_node,allocated_nodes,allocated_edges,last_value);
            if(!STALL && CHECK_CYCLES && cycle_count!==iterations[iteration_index][255:192])
                $fatal(1,"iteration %0d cycles actual=%0d expected=%0d",iteration_index,cycle_count,iterations[iteration_index][255:192]);
            iteration_index=iteration_index+1;
        end
    end
    initial begin
        if(!$value$plusargs("FIXTURE=%s",directory) || !$value$plusargs("EVENTS=%s",event_path) ||
           !$value$plusargs("COUNT=%d",count) || !$value$plusargs("ADC=%d",adc_count) ||
           !$value$plusargs("ITERATIONS=%d",iteration_count) || !$value$plusargs("HIDDEN_SHIFT=%d",hidden_setting) ||
           !$value$plusargs("LOGIT_SHIFT=%d",logit_setting) || !$value$plusargs("NODES=%d",nodes_cap) ||
           !$value$plusargs("EDGES=%d",edges_cap) || !$value$plusargs("PATH=%d",path_cap)) $fatal(1,"missing fixture arguments");
        events=$fopen(event_path,"w");
        for(i=0;i<393216;i=i+1) begin node_memory[i]=0; expected_node[i]=0; end
        for(i=0;i<131072;i=i+1) begin child_memory[i]=0; expected_child[i]=0; end
        $readmemh({directory,"/initial_node.hex"},node_memory); $readmemh({directory,"/initial_child.hex"},child_memory);
        $readmemh({directory,"/expected_node.hex"},expected_node); $readmemh({directory,"/expected_child.hex"},expected_child);
        $readmemh({directory,"/transactions.hex"},transactions,0,count-1);
        $readmemh({directory,"/adc.hex"},adc_vectors,0,adc_count-1);
        $readmemh({directory,"/iterations.hex"},iterations,0,iteration_count-1);
        tick(); tick(); @(negedge clk); rst_n=1;
        @(negedge clk); root_id=0; initial_nodes=1; initial_edges=0; iteration_limit=32'(iteration_count);
        node_limit=FAULT==3 ? 32'd1 : 32'(nodes_cap); edge_limit=32'(edges_cap); path_limit=32'(path_cap);
        seed=0; exploration_constant=64'h3ff69fbe76c8b439; hidden_shift=6'(hidden_setting); logit_shift=8'(logit_setting);
        start=1; #1; if(!ready) $fatal(1,"job not ready");
        tick(); @(negedge clk); start=0;
        root_id='1; initial_nodes=0; initial_edges='1; iteration_limit=0; seed=91; node_limit=0; edge_limit=0; path_limit=0;
        hidden_shift=0; logit_shift=0; exploration_constant=0;
        while(!result_valid) tick();
        saved_requests=transaction_index;
        repeat(4) begin tick(); if(!result_valid || ready || transaction_index!=saved_requests) $fatal(1,"job result not held"); end
        if(FAULT!=0) begin
            if((FAULT==1 && result_error!=8'h13) || (FAULT==2 && result_error!=8'h33) || (FAULT==3 && result_error!=8'h23))
                $fatal(1,"wrong propagated error %h",result_error);
        end else begin
            if(result_error!=0 || iteration_index!=iteration_count || transaction_index!=count || adc_index!=adc_count || current_depth!=0)
                $fatal(1,"incomplete search err=%h iterations=%0d transfers=%0d ADC=%0d",result_error,iteration_index,transaction_index,adc_index);
            for(i=0;i<393216;i=i+1) if(node_memory[i]!==expected_node[i]) $fatal(1,"node SRAM differs at %0d actual=%h expected=%h",i,node_memory[i],expected_node[i]);
            for(i=0;i<131072;i=i+1) if(child_memory[i]!==expected_child[i]) $fatal(1,"child SRAM differs at %0d",i);
        end
        @(negedge clk); result_ready=1; tick(); @(negedge clk); result_ready=0;
        if(ready || result_valid) $fatal(1,"new job accepted without coordinated reset");
        @(negedge clk); rst_n=0; tick(); @(negedge clk); rst_n=1; tick();
        if(!ready || result_error!=0) $fatal(1,"reset not ready");
        $display("tb_imc_buffered_iteration_core PASS iterations=%0d transfers=%0d stall=%0d fault=%0d",iteration_index,transaction_index,STALL,FAULT);
        $fclose(events); $finish;
    end
endmodule
