// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// UCB1 Calculator for 5x5 Go Board
// Computes UCB1 values for child selection in MCTS
// UCB1 = wins/visits + C * sqrt(log(parent_visits)/visits)

module ucb1_calculator_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [15:0] child_wins,         // Child win count
    input  logic [15:0] child_visits,       // Child visit count  
    input  logic [15:0] parent_visits,      // Parent visit count
    input  logic [15:0] exploration_constant, // UCB1 exploration parameter (C)
    output logic [31:0] ucb1_value,         // Fixed-point UCB1 result
    output logic        calculation_valid,
    output logic        calculation_complete,
    
    // Optional: expose intermediate values for debugging
    output logic [31:0] exploitation_term,  // wins/visits
    output logic [31:0] exploration_term    // C * sqrt(log(parent_visits)/visits)
);

    // Internal registers and wires
    logic [3:0]  state, next_state;
    logic [31:0] win_ratio;          // wins/visits (16.16 fixed point)
    logic [31:0] log_ratio;          // log(parent_visits/visits)
    logic [31:0] sqrt_log;           // sqrt(log_ratio)
    logic [31:0] exploration_val;    // C * sqrt_log
    logic [31:0] ucb1_result;
    
    // Divider and math units
    logic        div_start, div_valid;
    logic [31:0] div_quotient;
    logic        sqrt_start, sqrt_valid;
    logic [31:0] sqrt_result;
    logic        log_start, log_valid;
    logic [31:0] log_result;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam CHECK_VISITS = 4'b0001;
    localparam CALC_WIN_RATIO = 4'b0010;
    localparam WAIT_WIN_RATIO = 4'b0011;
    localparam CALC_VISIT_RATIO = 4'b0100;
    localparam WAIT_VISIT_RATIO = 4'b0101;
    localparam CALC_LOG = 4'b0110;
    localparam WAIT_LOG = 4'b0111;
    localparam CALC_SQRT = 4'b1000;
    localparam WAIT_SQRT = 4'b1001;
    localparam CALC_EXPLORATION = 4'b1010;
    localparam CALC_UCB1 = 4'b1011;
    localparam COMPLETE = 4'b1100;
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
        end else begin
            state <= next_state;
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        case (state)
            IDLE: if (enable) next_state = CHECK_VISITS;
            CHECK_VISITS: next_state = CALC_WIN_RATIO;
            CALC_WIN_RATIO: next_state = WAIT_WIN_RATIO;
            WAIT_WIN_RATIO: if (div_valid) next_state = CALC_VISIT_RATIO;
            CALC_VISIT_RATIO: next_state = WAIT_VISIT_RATIO;
            WAIT_VISIT_RATIO: if (div_valid) next_state = CALC_LOG;
            CALC_LOG: next_state = WAIT_LOG;
            WAIT_LOG: if (log_valid) next_state = CALC_SQRT;
            CALC_SQRT: next_state = WAIT_SQRT;
            WAIT_SQRT: if (sqrt_valid) next_state = CALC_EXPLORATION;
            CALC_EXPLORATION: next_state = CALC_UCB1;
            CALC_UCB1: next_state = COMPLETE;
            COMPLETE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end
    
    // Control signals
    assign div_start = (state == CALC_WIN_RATIO) || (state == CALC_VISIT_RATIO);
    assign log_start = (state == CALC_LOG);
    assign sqrt_start = (state == CALC_SQRT);
    
    // Fixed-point divider (simplified - would use IP in real synthesis)
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            div_valid <= 1'b0;
            div_quotient <= '0;
        end else if (div_start) begin
            div_valid <= 1'b0;
            // Simplified division for synthesis (would use dedicated divider IP)
            if (state == CALC_WIN_RATIO && child_visits != 0) begin
                div_quotient <= ({child_wins, 16'b0} / child_visits); // 16.16 fixed point
            end else if (state == CALC_VISIT_RATIO && child_visits != 0) begin
                div_quotient <= ({parent_visits, 16'b0} / child_visits);
            end else begin
                div_quotient <= 32'hFFFFFFFF; // Max value for unvisited nodes
            end
        end else if (div_start) begin
            div_valid <= 1'b1;
        end
    end
    
    // Logarithm calculation (lookup table or approximation)
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            log_valid <= 1'b0;
            log_result <= '0;
        end else if (log_start) begin
            log_valid <= 1'b0;
            // Simplified log calculation (would use CORDIC or LUT in real design)
            log_result <= div_quotient >> 2; // Simplified approximation
        end else if (log_start) begin
            log_valid <= 1'b1;
        end
    end
    
    // Square root calculation (CORDIC or approximation)
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sqrt_valid <= 1'b0;
            sqrt_result <= '0;
        end else if (sqrt_start) begin
            sqrt_valid <= 1'b0;
            // Simplified sqrt calculation (would use CORDIC in real design)
            sqrt_result <= log_result >> 1; // Simplified approximation
        end else if (sqrt_start) begin
            sqrt_valid <= 1'b1;
        end
    end
    
    // Register intermediate and final results
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            win_ratio <= '0;
            log_ratio <= '0;
            sqrt_log <= '0;
            exploration_val <= '0;
            ucb1_result <= '0;
        end else begin
            case (state)
                WAIT_WIN_RATIO: if (div_valid) win_ratio <= div_quotient;
                WAIT_VISIT_RATIO: if (div_valid) log_ratio <= div_quotient;
                WAIT_LOG: if (log_valid) log_ratio <= log_result;
                WAIT_SQRT: if (sqrt_valid) sqrt_log <= sqrt_result;
                CALC_EXPLORATION: exploration_val <= (exploration_constant * sqrt_log) >> 16;
                CALC_UCB1: ucb1_result <= win_ratio + exploration_val;
            endcase
        end
    end
    
    // Handle unvisited children (assign maximum UCB1 value)
    logic unvisited_child;
    assign unvisited_child = (child_visits == 0);
    
    // Output assignments
    assign exploitation_term = win_ratio;
    assign exploration_term = exploration_val;
    assign ucb1_value = unvisited_child ? 32'hFFFFFFFF : ucb1_result;
    assign calculation_valid = (state == COMPLETE);
    assign calculation_complete = (state == COMPLETE);
    
endmodule
