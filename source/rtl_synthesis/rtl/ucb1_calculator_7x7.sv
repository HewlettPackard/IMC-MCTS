// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// UCB1 Calculator for 7x7 Go Board
// Computes UCB1 values for all child nodes in MCTS selection
// Optimized for 49-child parallel computation with proper scaling

module ucb1_calculator_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [31:0] parent_visit_count,  // Parent node visit count
    input  logic [31:0] child_visit_counts [0:48], // Visit counts for 49 children
    input  logic [31:0] child_win_counts [0:48],   // Win counts for 49 children
    input  logic [5:0]  num_children,       // Number of valid children (0-49)
    input  logic [15:0] exploration_constant, // UCB1 exploration parameter (C)
    output logic [15:0] ucb1_values [0:48],  // UCB1 values for each child
    output logic [5:0]  best_child_index,   // Index of child with highest UCB1
    output logic        calculation_complete,
    output logic        values_valid
);

    // Internal registers  
    logic [2:0]  state, next_state;
    logic [5:0]  calc_counter;
    logic [15:0] ucb1_buffer [0:48];         // Buffer for 49 UCB1 values
    logic [15:0] current_ucb1;
    logic [15:0] best_ucb1;
    logic [5:0]  best_index;
    logic [5:0]  current_child;
    
    // Intermediate calculation registers
    logic [15:0] win_rate;                   // Fixed-point win rate
    logic [15:0] confidence_interval;        // UCB1 confidence term
    logic [31:0] log_parent_visits;          // log(parent_visit_count)
    logic [31:0] exploration_term;
    
    // State encoding
    localparam IDLE = 3'b000;
    localparam SETUP_CALC = 3'b001;
    localparam CALCULATE_UCB1 = 3'b010;
    localparam UPDATE_BEST = 3'b011;
    localparam NEXT_CHILD = 3'b100;
    localparam COMPLETE = 3'b101;
    
    // Fixed-point arithmetic constants (16-bit fixed point)
    localparam [31:0] FIXED_POINT_ONE = 32'h10000;  // 1.0 in 16.16 fixed point
    localparam [15:0] SQRT_2 = 16'h16A09;           // sqrt(2) in 16-bit fixed point
    
    // Lookup table for logarithm approximation (for UCB1 calculation)
    logic [15:0] log_lut [0:255];
    
    // Initialize logarithm lookup table
    initial begin
        for (int i = 0; i < 256; i++) begin
            // Approximate log(i+1) in fixed-point format
            log_lut[i] = 16'h0000; // Simplified - would need proper log values
        end
    end
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            calc_counter <= '0;
            current_child <= '0;
            best_ucb1 <= '0;
            best_index <= '0;
            // Initialize UCB1 buffer
            for (int i = 0; i < 49; i++) begin
                ucb1_buffer[i] <= '0;
            end
        end else begin
            state <= next_state;
            
            case (state)
                SETUP_CALC: begin
                    calc_counter <= '0;
                    current_child <= '0;
                    best_ucb1 <= '0;
                    best_index <= '0;
                    // Precompute log(parent_visit_count) for efficiency
                    if (parent_visit_count > 0 && parent_visit_count < 256)
                        log_parent_visits <= {16'h0, log_lut[parent_visit_count[7:0]]};
                    else
                        log_parent_visits <= FIXED_POINT_ONE;
                end
                
                CALCULATE_UCB1: begin
                    if (current_child < 49 && current_child < num_children) begin
                        // Calculate win rate (avoid division by zero)
                        if (child_visit_counts[current_child] > 0) begin
                            win_rate <= (child_win_counts[current_child] << 16) / 
                                       child_visit_counts[current_child];
                        end else begin
                            win_rate <= 16'hFFFF; // Maximum value for unvisited nodes
                        end
                        
                        // Calculate confidence interval
                        if (child_visit_counts[current_child] > 0) begin
                            exploration_term <= (log_parent_visits << 1) / child_visit_counts[current_child];
                            confidence_interval <= (exploration_constant * SQRT_2 * 
                                                   exploration_term[15:0]) >> 8;
                        end else begin
                            confidence_interval <= 16'hFFFF; // Maximum for unvisited
                        end
                        
                        // Combine win rate and confidence interval
                        current_ucb1 <= win_rate + confidence_interval;
                        ucb1_buffer[current_child] <= win_rate + confidence_interval;
                    end
                end
                
                UPDATE_BEST: begin
                    if (current_child < 49 && current_child < num_children) begin
                        if (current_ucb1 > best_ucb1) begin
                            best_ucb1 <= current_ucb1;
                            best_index <= current_child;
                        end
                    end
                end
                
                NEXT_CHILD: begin
                    if (calc_counter < num_children - 1 && calc_counter < 48) begin
                        calc_counter <= calc_counter + 1;
                        current_child <= calc_counter + 1;
                    end
                end
                
                IDLE: begin
                    calc_counter <= '0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        
        case (state)
            IDLE: begin
                if (enable && num_children > 0)
                    next_state = SETUP_CALC;
            end
            
            SETUP_CALC:
                next_state = CALCULATE_UCB1;
                
            CALCULATE_UCB1:
                next_state = UPDATE_BEST;
                
            UPDATE_BEST: begin
                if (calc_counter < num_children - 1 && calc_counter < 48)
                    next_state = NEXT_CHILD;
                else
                    next_state = COMPLETE;
            end
            
            NEXT_CHILD:
                next_state = CALCULATE_UCB1;
                
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // Output assignments
    genvar i;
    generate
        for (i = 0; i < 49; i++) begin : ucb1_assign
            assign ucb1_values[i] = ucb1_buffer[i];
        end
    endgenerate
    
    assign best_child_index = best_index;
    assign calculation_complete = (state == COMPLETE);
    assign values_valid = (state == COMPLETE);

endmodule
