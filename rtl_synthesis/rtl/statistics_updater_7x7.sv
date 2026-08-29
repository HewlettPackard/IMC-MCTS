// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Statistics Updater for 7x7 Go Board
// Updates visit counts and win statistics for MCTS nodes during backpropagation
// Supports incremental updates with overflow protection for 7x7 game complexity

module statistics_updater_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        update_enable,       // Signal to perform statistics update
    input  logic [15:0] node_address,        // Address of node to update
    input  logic [1:0]  rollout_result,      // Rollout outcome (01=black win, 10=white win, 00=draw)
    input  logic        current_player,      // Player perspective for win rate calculation
    input  logic [31:0] old_visit_count,     // Previous visit count for this node
    input  logic [31:0] old_win_count,       // Previous win count for this node
    input  logic [31:0] parent_visit_count,  // Parent node visit count for UCB1 calculation
    output logic [31:0] new_visit_count,     // Updated visit count
    output logic [31:0] new_win_count,       // Updated win count
    output logic [15:0] new_win_rate,        // Updated win rate (fixed-point format)
    output logic [15:0] new_ucb1_value,      // Updated UCB1 value for node selection
    output logic        update_complete,     // Signal indicating update finished
    output logic        statistics_valid,    // Validity flag for updated statistics
    output logic        overflow_error,      // Flag indicating arithmetic overflow
    output logic [15:0] confidence_interval  // UCB1 confidence component
);

    // Internal registers
    logic [2:0]  state, next_state;
    logic [31:0] temp_visit_count;
    logic [31:0] temp_win_count;
    logic [15:0] temp_win_rate;
    logic [15:0] temp_ucb1_value;
    logic [15:0] temp_confidence;
    logic        overflow_flag;
    logic        underflow_flag;
    
    // State encoding
    localparam IDLE = 3'b000;
    localparam UPDATE_VISITS = 3'b001;
    localparam UPDATE_WINS = 3'b010;
    localparam CALCULATE_RATE = 3'b011;
    localparam CALCULATE_UCB1 = 3'b100;
    localparam VALIDATE_RESULTS = 3'b101;
    localparam COMPLETE = 3'b110;
    
    // Fixed-point arithmetic constants (16.16 format for intermediate calculations)
    localparam [31:0] FIXED_POINT_ONE = 32'h10000;  // 1.0 in 16.16 fixed point
    localparam [15:0] UCB1_CONSTANT = 16'h16A09;    // sqrt(2) approximation
    localparam [31:0] MAX_COUNT = 32'hFFFFFFF0;     // Maximum count before overflow protection
    
    // Logarithm approximation for UCB1 calculation
    logic [15:0] log_approximation;
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            temp_visit_count <= '0;
            temp_win_count <= '0;
            temp_win_rate <= '0;
            temp_ucb1_value <= '0;
            temp_confidence <= '0;
            overflow_flag <= 1'b0;
            underflow_flag <= 1'b0;
        end else begin
            state <= next_state;
            
            case (state)
                UPDATE_VISITS: begin
                    // Increment visit count with overflow protection
                    if (old_visit_count < MAX_COUNT) begin
                        temp_visit_count <= old_visit_count + 1;
                        overflow_flag <= 1'b0;
                    end else begin
                        temp_visit_count <= MAX_COUNT;
                        overflow_flag <= 1'b1;
                    end
                end
                
                UPDATE_WINS: begin
                    // Update win count based on rollout result and player perspective
                    temp_win_count <= old_win_count;
                    
                    case (rollout_result)
                        2'b01: begin // Black wins
                            if (!current_player && old_win_count < MAX_COUNT) begin
                                temp_win_count <= old_win_count + 1;
                            end else if (current_player) begin
                                // White perspective - no win increment
                                temp_win_count <= old_win_count;
                            end
                        end
                        
                        2'b10: begin // White wins
                            if (current_player && old_win_count < MAX_COUNT) begin
                                temp_win_count <= old_win_count + 1;
                            end else if (!current_player) begin
                                // Black perspective - no win increment
                                temp_win_count <= old_win_count;
                            end
                        end
                        
                        2'b00: begin // Draw
                            // For draws, increment by 0.5 (represented as +0 for simplicity)
                            // In more sophisticated implementation, could use fractional counting
                            temp_win_count <= old_win_count;
                        end
                        
                        default: begin
                            temp_win_count <= old_win_count;
                        end
                    endcase
                    
                    // Check for win count overflow
                    if (temp_win_count > temp_visit_count) begin
                        temp_win_count <= temp_visit_count; // Cap at visit count
                        overflow_flag <= 1'b1;
                    end
                end
                
                CALCULATE_RATE: begin
                    // Calculate win rate as fixed-point (Q8.8 format for 16-bit result)
                    if (temp_visit_count > 0) begin
                        temp_win_rate <= (temp_win_count << 8) / temp_visit_count;
                    end else begin
                        temp_win_rate <= 16'h0000; // 0% win rate for unvisited nodes
                    end
                end
                
                CALCULATE_UCB1: begin
                    // Calculate UCB1 value: win_rate + C * sqrt(ln(parent_visits) / node_visits)
                    if (temp_visit_count > 0 && parent_visit_count > 0) begin
                        // Simplified logarithm approximation
                        if (parent_visit_count < 256) begin
                            log_approximation <= parent_visit_count[7:0] << 4; // Rough approximation
                        end else begin
                            log_approximation <= 16'hFF0; // Saturate for large values
                        end
                        
                        // Calculate confidence interval: C * sqrt(ln(N) / n)
                        temp_confidence <= (UCB1_CONSTANT * log_approximation) / temp_visit_count[15:0];
                        
                        // Combine win rate and confidence
                        temp_ucb1_value <= temp_win_rate + temp_confidence;
                    end else begin
                        // Unvisited nodes get maximum UCB1 value
                        temp_ucb1_value <= 16'hFFFF;
                        temp_confidence <= 16'hFFFF;
                    end
                end
                
                VALIDATE_RESULTS: begin
                    // Validate all calculated values for consistency
                    if (temp_win_count > temp_visit_count) begin
                        temp_win_count <= temp_visit_count;
                        overflow_flag <= 1'b1;
                    end
                    
                    if (temp_win_rate > 16'hFF00) begin // Win rate > 99.6%
                        temp_win_rate <= 16'hFF00;
                    end
                    
                    // Check for underflow conditions
                    if (temp_visit_count == 0 && (temp_win_count > 0 || temp_win_rate > 0)) begin
                        underflow_flag <= 1'b1;
                        temp_win_count <= '0;
                        temp_win_rate <= '0;
                    end
                end
                
                IDLE: begin
                    overflow_flag <= 1'b0;
                    underflow_flag <= 1'b0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        
        case (state)
            IDLE: begin
                if (update_enable)
                    next_state = UPDATE_VISITS;
            end
            
            UPDATE_VISITS:
                next_state = UPDATE_WINS;
                
            UPDATE_WINS:
                next_state = CALCULATE_RATE;
                
            CALCULATE_RATE:
                next_state = CALCULATE_UCB1;
                
            CALCULATE_UCB1:
                next_state = VALIDATE_RESULTS;
                
            VALIDATE_RESULTS:
                next_state = COMPLETE;
                
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // Statistics validation
    logic stats_consistency_valid;
    always_comb begin
        stats_consistency_valid = (temp_win_count <= temp_visit_count) &&
                                  !overflow_flag &&
                                  !underflow_flag &&
                                  (temp_visit_count > 0 || temp_win_count == 0);
    end
    
    // Output assignments
    assign new_visit_count = temp_visit_count;
    assign new_win_count = temp_win_count;
    assign new_win_rate = temp_win_rate;
    assign new_ucb1_value = temp_ucb1_value;
    assign update_complete = (state == COMPLETE);
    assign statistics_valid = (state == COMPLETE) && stats_consistency_valid;
    assign overflow_error = overflow_flag || underflow_flag;
    assign confidence_interval = temp_confidence;

endmodule
