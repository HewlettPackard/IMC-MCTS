// Parallel arithmetic, partial batches, ties, held output, errors and reset.
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_ucb_batch_overlap;
    logic clk=0, rst_n=0;
    logic batch_req_valid=0, batch_req_ready;
    logic [2:0] batch_count=0;
    logic [31:0] batch_parent_visits=0;
    logic [63:0] batch_exploration=0;
    logic [127:0] batch_child_ids=0, batch_child_visits=0;
    logic [255:0] batch_child_values=0;
    logic batch_rsp_valid, batch_rsp_ready=0, batch_rsp_error;
    logic [31:0] batch_rsp_child;
    logic [63:0] batch_rsp_score;
    logic [3:0] debug_lane_active;
    integer cycle=0, started, i, n;
    integer active [0:3];
    imc_ucb_batch_overlap dut (.*);
    always #5 clk=~clk;
    always @(posedge clk) cycle=cycle+1;
    task automatic tick;
        @(posedge clk); #1;
    endtask
    task automatic request(input logic [2:0] count);
        @(negedge clk);
        batch_count=count; batch_req_valid=1;
        #1; if (!batch_req_ready) $fatal(1,"not ready");
        tick(); started=cycle;
        for (i=0;i<4;i=i+1) active[i]=debug_lane_active[i] ? 1 : 0;
        @(negedge clk); batch_req_valid=0;
        batch_count=0; batch_parent_visits=0; batch_exploration='1;
        batch_child_ids='1; batch_child_visits='1; batch_child_values='1;
    endtask
    task automatic finish(input logic [31:0] child, input logic [63:0] score,
                          input logic error, input integer count);
        while (!batch_rsp_valid) begin
            tick();
            for (i=0;i<4;i=i+1) if (debug_lane_active[i]) active[i]=active[i]+1;
        end
        if (batch_rsp_error !== error) $fatal(1,"wrong error");
        if (!error && (batch_rsp_child !== child || batch_rsp_score !== score))
            $fatal(1,"wrong result child=%0d score=%h",batch_rsp_child,batch_rsp_score);
        if (!error && cycle-started != 169+count)
            $fatal(1,"wrong latency actual=%0d expected=%0d",cycle-started,169+count);
        if (!error)
            for (i=0;i<4;i=i+1)
                if (active[i] != ((i<count) ? 169 : 0)) $fatal(1,"wrong lane occupancy");
        $display("batch count=%0d latency=%0d error=%0d",count,cycle-started,error);
        repeat (3) begin
            tick();
            if (!batch_rsp_valid || batch_req_ready || batch_rsp_error !== error)
                $fatal(1,"result not held");
            if (!error && (batch_rsp_child !== child || batch_rsp_score !== score))
                $fatal(1,"held result changed");
        end
        @(negedge clk); batch_rsp_ready=1;
        tick(); @(negedge clk); batch_rsp_ready=0;
    endtask
    task automatic operands;
        batch_parent_visits=10; batch_exploration=0;
        batch_child_ids={32'd103,32'd102,32'd101,32'd100};
        batch_child_visits={32'd10,32'd10,32'd10,32'd10};
        batch_child_values={64'h4014000000000000,64'h4014000000000000,
                            64'h4014000000000000,64'h4014000000000000};
    endtask
    initial begin
        tick(); tick(); @(negedge clk); rst_n=1;
        for (n=1;n<=4;n=n+1) begin
            operands(); request(3'(n)); finish(100,64'h3fe0000000000000,0,n);
        end
        operands(); batch_child_values[64 +: 64]=0;
        request(2); finish(101,64'h3ff0000000000000,0,2);
        operands(); batch_child_values[192 +: 64]=0;
        request(4); finish(103,64'h3ff0000000000000,0,4);
        operands(); batch_exploration=64'h3ff0000000000000;
        batch_parent_visits=1; batch_child_visits={4{32'd1}}; batch_child_values=0;
        request(4); finish(100,64'h3ff0000000000000,0,4);
        operands(); batch_parent_visits=37; batch_exploration=64'h3ff69fbe76c8b439;
        batch_child_visits={32'd9,32'd7,32'd5,32'd3};
        batch_child_values={64'h4008000000000000,64'h4014000000000000,
                            64'h4000000000000000,64'h3ff8000000000000};
        request(4); finish(100,64'h4000691357380000,0,4);
        operands(); batch_child_visits[32 +: 32]=0;
        request(4); finish(0,0,1,4);
        operands(); request(0); finish(0,0,1,0);
        operands(); request(5); finish(0,0,1,5);
        operands(); request(4); repeat(100) tick();
        @(negedge clk); rst_n=0; tick();
        if (batch_rsp_valid || batch_req_ready || debug_lane_active != 0) $fatal(1,"reset did not abort");
        @(negedge clk); rst_n=1; tick();
        operands(); request(4); finish(100,64'h3fe0000000000000,0,4);
        $display("tb_imc_ucb_batch_overlap PASS"); $finish;
    end
endmodule
