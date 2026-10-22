// Check packed expansion/backpropagation requests and complete SRAM state.
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_tree_update #(
    parameter int BOARD_SIZE=2, CAM_ENTRIES=7, NEURAL_BYTES=16424,
    parameter int STALL=0, FAULT=0, ADDR_W=21
);
    logic clk = '0;
    logic rst_n = '0;
    logic start = '0;
    logic ready;
    logic backpropagate = '0;
    logic [31:0] selected_node = '0;
    logic [31:0] nodes_used = '0;
    logic [31:0] edges_used = '0;
    logic [31:0] selected_depth = '0;
    logic [31:0] node_limit = '0;
    logic [31:0] edge_limit = '0;
    logic [31:0] path_limit = '0;
    logic [31:0] choice_word = '0;
    logic [31:0] value_q17 = '0;
    logic result_valid;
    logic result_ready = '0;
    logic [31:0] result_node;
    logic [31:0] result_nodes_used;
    logic [31:0] result_edges_used;
    logic [31:0] result_depth;
    logic [31:0] nodes_changed;
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
    logic child_req_write;
    logic [ADDR_W-1:0] child_req_addr;
    logic [31:0] child_req_wdata;
    logic child_rsp_valid = '0;
    logic child_rsp_ready;
    logic [31:0] child_rsp_rdata = '0;
    logic child_rsp_error = '0;
    logic [5:0] debug_state;

`ifdef IMC_POST_SYNTH
    imc_tree_update dut (.*);
`else
    imc_tree_update #(.BOARD_SIZE(BOARD_SIZE),.CAM_ENTRIES(CAM_ENTRIES),.NEURAL_BYTES(NEURAL_BYTES)) dut (.*);
`endif
    always #5 clk=~clk;
    logic [31:0] node_memory [0:393215], child_memory [0:131071];
    logic [31:0] expected_node [0:393215], expected_child [0:131071];
    logic [63:0] transactions [0:4095];
    logic [511:0] commands [0:1], descriptor;
    logic [31:0] ends [0:1];
    logic [63:0] expected;
    logic [31:0] data, pending_data;
    logic pending=0, pending_child=0, pending_error=0, fault_fired=0;
    integer delay_count=0, cycle=0, transaction_index=0, command_index=0;
    integer i, count, command_count, events, start_cycle, saved_requests;
    string directory, event_path;
    task automatic tick;
        @(posedge clk); #1;
    endtask
    task automatic release_result;
        saved_requests=transaction_index;
        repeat (4) begin
            tick();
            if (!result_valid || ready || node_req_valid || child_req_valid || transaction_index!=saved_requests)
                $fatal(1,"completion backpressure changed work");
        end
        @(negedge clk); result_ready=1;
        tick();
        @(negedge clk); result_ready=0;
    endtask
    task automatic access(input logic child, input logic write_enable, input logic [ADDR_W-1:0] address, input logic [31:0] wdata);
        begin
            data=write_enable ? wdata : (child ? child_memory[address/4] : node_memory[address/4]);
            if (!fault_fired) begin
                if (transaction_index>=count) $fatal(1,"extra memory transfer");
                expected=transactions[transaction_index];
                if ({child,write_enable,30'(address),data} !== expected)
                    $fatal(1,"transaction %0d differs actual=%h expected=%h",transaction_index,{child,write_enable,30'(address),data},expected);
            end
            transaction_index=transaction_index+1;
            $fdisplay(events,"memory,%0d,%0d,%0d,%0d,%0d,%08x",command_index,cycle,child,write_enable,address,data);
            pending=1; pending_child=child; pending_data=data;
            delay_count=1+(STALL ? cycle%3 : 0);
            pending_error=0;
            if (!fault_fired && ((FAULT==1 && !child && !write_enable) || (FAULT==2 && !child && write_enable) || (FAULT==3 && child))) begin
                pending_error=1; fault_fired=1;
            end
            if (write_enable) begin
                if (child) child_memory[address/4]<=wdata;
                else node_memory[address/4]<=wdata;
            end
        end
    endtask
    always @(negedge clk) begin
        node_req_ready=rst_n && !pending && !node_rsp_valid && !child_rsp_valid && (!STALL || cycle%5!=0);
        child_req_ready=node_req_ready;
    end
    always @(posedge clk) begin
        cycle=cycle+1;
        if (!rst_n) begin
            pending=0; node_rsp_valid<=0; child_rsp_valid<=0; node_rsp_error<=0; child_rsp_error<=0;
        end else begin
            if (node_rsp_valid && node_rsp_ready) node_rsp_valid<=0;
            if (child_rsp_valid && child_rsp_ready) child_rsp_valid<=0;
            if (pending) begin
                if (delay_count==1) begin
                    if (pending_child) begin child_rsp_valid<=1; child_rsp_rdata<=pending_data; child_rsp_error<=pending_error; end
                    else begin node_rsp_valid<=1; node_rsp_rdata<=pending_data; node_rsp_error<=pending_error; end
                    pending=0;
                end else delay_count=delay_count-1;
            end
            if (node_req_valid && child_req_valid) $fatal(1,"overlapping memory interfaces");
            if (node_req_valid && node_req_ready) access(0,node_req_write,node_req_addr,node_req_wdata);
            if (child_req_valid && child_req_ready) access(1,child_req_write,child_req_addr,child_req_wdata);
        end
    end
    initial begin
        if (!$value$plusargs("FIXTURE=%s",directory)) $fatal(1,"FIXTURE missing");
        if (!$value$plusargs("EVENTS=%s",event_path)) $fatal(1,"EVENTS missing");
        if (!$value$plusargs("COUNT=%d",count)) $fatal(1,"COUNT missing");
        if (!$value$plusargs("COMMANDS=%d",command_count)) $fatal(1,"COMMANDS missing");
        events=$fopen(event_path,"w");
        for(i=0;i<393216;i=i+1) begin node_memory[i]=0; expected_node[i]=0; end
        for(i=0;i<131072;i=i+1) begin child_memory[i]=0; expected_child[i]=0; end
        $readmemh({directory,"/initial_node.hex"},node_memory);
        $readmemh({directory,"/initial_child.hex"},child_memory);
        $readmemh({directory,"/expected_node.hex"},expected_node);
        $readmemh({directory,"/expected_child.hex"},expected_child);
        $readmemh({directory,"/commands.hex"},commands,0,command_count-1);
        $readmemh({directory,"/ends.hex"},ends,0,command_count-1);
        $readmemh({directory,"/transactions.hex"},transactions,0,count-1);
        tick(); tick(); @(negedge clk); rst_n=1;
        for(command_index=0;command_index<command_count;command_index=command_index+1) begin
            descriptor=commands[command_index];
            @(negedge clk);
            backpropagate=descriptor[0]; selected_node=descriptor[63:32]; nodes_used=descriptor[95:64];
            edges_used=descriptor[127:96]; selected_depth=descriptor[159:128]; node_limit=descriptor[191:160];
            edge_limit=descriptor[223:192]; path_limit=descriptor[255:224]; choice_word=descriptor[287:256]; value_q17=descriptor[319:288];
            start=1; #1; if(!ready) $fatal(1,"start not ready");
            tick(); start_cycle=cycle;
            @(negedge clk); start=0; backpropagate=0; selected_node='1; nodes_used=0; edges_used=0;
            selected_depth=0; node_limit=0; edge_limit=0; path_limit=0; choice_word=0; value_q17='1;
            while(!result_valid) tick();
            $fdisplay(events,"result,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",command_index,cycle-start_cycle,result_node,result_nodes_used,result_edges_used,result_depth,nodes_changed,result_error);
            if(fault_fired) begin
                if(result_error!=2 || !poisoned) $fatal(1,"memory fault did not propagate");
                release_result();
                @(negedge clk); start=1; tick(); @(negedge clk); start=0;
                if(!result_valid || result_error!=8) $fatal(1,"poisoned retry was accepted");
                release_result();
                @(negedge clk); rst_n=0; tick(); tick();
                if(poisoned || result_valid) $fatal(1,"reset did not clear failed operation");
                $display("tb_imc_tree_update PASS fault=%0d",FAULT); $fclose(events); $finish;
            end
            if(32'(result_error)!==descriptor[511:480]) $fatal(1,"unexpected result error %0d",result_error);
            if(transaction_index!=int'(ends[command_index])) $fatal(1,"memory traffic incomplete");
            if(!result_error && {nodes_changed,result_depth,result_edges_used,result_nodes_used,result_node} !== descriptor[479:320])
                $fatal(1,"result counters or selected child differ");
            if(result_error!=0 && !poisoned) $fatal(1,"runtime error did not poison");
            release_result();
        end
        if(FAULT!=0) $fatal(1,"fault was not exercised");
        for(i=0;i<393216;i=i+1) if(node_memory[i]!==expected_node[i]) $fatal(1,"node SRAM differs at %0d actual=%h expected=%h",i,node_memory[i],expected_node[i]);
        for(i=0;i<131072;i=i+1) if(child_memory[i]!==expected_child[i]) $fatal(1,"child SRAM differs at %0d",i);
        $display("tb_imc_tree_update PASS commands=%0d transactions=%0d stall=%0d",command_count,transaction_index,STALL);
        $fclose(events); $finish;
    end
endmodule
