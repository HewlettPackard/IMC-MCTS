// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Selection Unit - UCB1 Calculator
// 2x2 Board Accelerator Architecture
// ============================================================================

module ucb1_calculator (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    input  logic [7:0] child_0_wins,
    input  logic [7:0] child_0_visits,
    input  logic [7:0] child_1_wins,
    input  logic [7:0] child_1_visits,
    input  logic [7:0] child_2_wins,
    input  logic [7:0] child_2_visits,
    input  logic [7:0] child_3_wins,
    input  logic [7:0] child_3_visits,
    input  logic [7:0] parent_visits,
    input  logic [7:0] exploration_const,
    input  logic [3:0] child_valid,
    
    output logic [15:0] ucb1_value_0,
    output logic [15:0] ucb1_value_1,
    output logic [15:0] ucb1_value_2,
    output logic [15:0] ucb1_value_3,
    output logic        calculation_done
);

    // UCB1 calculation function (simplified for 2x2)
    function automatic logic [15:0] calculate_ucb1(
        logic [7:0] wins, 
        logic [7:0] visits, 
        logic [7:0] parent_vis,
        logic [7:0] c_param
    );
        logic [15:0] exploitation, exploration;
        
        if (visits == 8'h0) begin
            return 16'hFFFF; // Max value for unvisited nodes
        end else begin
            // Simplified UCB1: wins/visits + c * sqrt(ln(parent_visits)/visits)
            // Using fixed-point arithmetic approximation
            exploitation = {8'h0, wins}; // Simple ratio approximation
            exploration = {8'h0, c_param}; // Simplified exploration term
            return exploitation + exploration;
        end
    endfunction

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ucb1_value_0     <= 16'h0;
            ucb1_value_1     <= 16'h0;
            ucb1_value_2     <= 16'h0;
            ucb1_value_3     <= 16'h0;
            calculation_done <= 1'b0;
        end else if (enable) begin
            // Parallel UCB1 calculation for all children
            ucb1_value_0 <= child_valid[0] ? 
                calculate_ucb1(child_0_wins, child_0_visits, parent_visits, exploration_const) : 16'h0;
            ucb1_value_1 <= child_valid[1] ? 
                calculate_ucb1(child_1_wins, child_1_visits, parent_visits, exploration_const) : 16'h0;
            ucb1_value_2 <= child_valid[2] ? 
                calculate_ucb1(child_2_wins, child_2_visits, parent_visits, exploration_const) : 16'h0;
            ucb1_value_3 <= child_valid[3] ? 
                calculate_ucb1(child_3_wins, child_3_visits, parent_visits, exploration_const) : 16'h0;
            calculation_done <= 1'b1;
        end else begin
            calculation_done <= 1'b0;
        end
    end

endmodule
