// Exact old/new score vectors, held results, repeated transactions and reset.
// SPDX-License-Identifier: MIT
`timescale 1ns/1ps
module tb_imc_ucb_score_overlap #(
    parameter int VECTOR_COUNT = 1,
    parameter VECTORS = "vectors.hex"
);
    logic clk=0, rst_n=0;
    logic score_req_valid=0, score_req_ready;
    logic [31:0] score_parent_visits=0, score_child_visits=0;
    logic [63:0] score_child_value=0, score_exploration=0;
    logic score_rsp_valid, score_rsp_ready=0, score_rsp_error;
    logic [63:0] score_rsp_value;
    logic [3:0] debug_state;
    logic old_ready, old_valid, old_error;
    logic [63:0] old_value;
    logic [3:0] old_state;
    logic [287:0] fixtures [0:VECTOR_COUNT-1];
    logic [63:0] expected;
    logic expected_error;
    integer cycle=0, started, old_latency, new_latency, i, j, abort_at;
    imc_ucb_score_overlap dut (.*);
    imc_ucb_score reference (
        .clk(clk), .rst_n(rst_n), .score_req_valid(score_req_valid),
        .score_req_ready(old_ready), .score_parent_visits(score_parent_visits),
        .score_child_visits(score_child_visits), .score_child_value(score_child_value),
        .score_exploration(score_exploration), .score_rsp_valid(old_valid),
        .score_rsp_ready(score_rsp_ready), .score_rsp_value(old_value),
        .score_rsp_error(old_error), .debug_state(old_state)
    );
    always #5 clk=~clk;
    always @(posedge clk) cycle=cycle+1;
    task automatic tick;
        @(posedge clk); #1;
    endtask
    task automatic launch(input integer index);
        @(negedge clk);
        score_parent_visits=fixtures[index][287:256];
        score_child_visits=fixtures[index][255:224];
        score_child_value=fixtures[index][223:160];
        score_exploration=fixtures[index][159:96];
        expected=fixtures[index][95:32]; expected_error=fixtures[index][0];
        score_req_valid=1;
        #1; if (!score_req_ready || !old_ready) $fatal(1,"request not ready");
        tick(); started=cycle;
        old_latency=old_valid ? 0 : -1;
        new_latency=score_rsp_valid ? 0 : -1;
        @(negedge clk); score_req_valid=0;
        score_parent_visits=0; score_child_visits=0;
        score_child_value='1; score_exploration='1;
    endtask
    task automatic finish;
        for (j=1;j<=222;j=j+1) begin
            tick();
            if (old_valid && old_latency<0) old_latency=cycle-started;
            if (score_rsp_valid && new_latency<0) new_latency=cycle-started;
            if (score_rsp_valid && (score_rsp_value !== expected || score_rsp_error !== expected_error))
                $fatal(1,"candidate mismatch vector=%0d actual=%h expected=%h error=%b",i,score_rsp_value,expected,score_rsp_error);
        end
        if (!old_valid || !score_rsp_valid || old_value !== expected || old_error !== expected_error)
            $fatal(1,"reference/result mismatch vector=%0d",i);
        if (!expected_error && (old_latency!=222 || new_latency!=168))
            $fatal(1,"wrong latency old=%0d new=%0d",old_latency,new_latency);
        if (expected_error && (old_latency!=0 || new_latency!=0)) $fatal(1,"invalid input not rejected immediately");
        @(negedge clk); score_req_valid=1;
        repeat (3) begin
            tick();
            if (!old_valid || !score_rsp_valid || score_req_ready || old_ready ||
                score_rsp_value !== expected || old_value !== expected ||
                score_rsp_error !== expected_error || old_error !== expected_error)
                $fatal(1,"response changed under backpressure or busy request");
        end
        @(negedge clk); score_req_valid=0; score_rsp_ready=1;
        tick(); @(negedge clk); score_rsp_ready=0;
        if (!score_req_ready || !old_ready || old_valid || score_rsp_valid) $fatal(1,"failed to retire");
    endtask
    initial begin
        $readmemh(VECTORS,fixtures);
        tick(); tick(); @(negedge clk); rst_n=1;
        for (i=0;i<VECTOR_COUNT;i=i+1) begin
            launch(i); finish();
        end
        for (abort_at=5;abort_at<=170;abort_at=abort_at+45) begin
            launch(0); repeat(abort_at) tick();
            @(negedge clk); rst_n=0; tick();
            if (score_rsp_valid || old_valid || score_req_ready || old_ready) $fatal(1,"reset did not abort");
            @(negedge clk); rst_n=1; tick();
            launch(0); finish();
        end
        $display("single scorer cycles: old=222 new=168 saved=54");
        $display("tb_imc_ucb_score_overlap PASS vectors=%0d",VECTOR_COUNT);
        $finish;
    end
endmodule
