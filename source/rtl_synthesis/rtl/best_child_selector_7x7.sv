// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Best Child Selector for 7x7 Go Board
// Selects the child with highest UCB1 value for MCTS tree traversal
// Supports 49-way selection with tie-breaking and validation

module best_child_selector_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [15:0] ucb1_values [0:48],  // UCB1 values for 49 children
    input  logic [5:0]  num_children,       // Number of valid children (0-49)
    input  logic [31:0] child_visit_counts [0:48], // For tie-breaking
    input  logic [15:0] tie_break_seed,     // Random seed for tie-breaking
    output logic [5:0]  selected_child,     // Index of selected child
    output logic [15:0] selected_ucb1,      // UCB1 value of selected child
    output logic        selection_valid,
    output logic        selection_complete,
    
    // Additional selection information
    output logic [5:0]  num_tied_children,  // Number of children tied for best
    output logic [5:0]  second_best_child,  // Index of second-best child
    output logic [15:0] max_ucb1_value      // Maximum UCB1 value found
);

    // Internal registers
    logic [2:0]  state, next_state;
    logic [5:0]  search_counter;
    logic [5:0]  current_child;
    logic [15:0] current_max_ucb1;
    logic [5:0]  current_best_child;
    logic [5:0]  current_second_best;
    logic [5:0]  tie_count;
    logic [5:0]  tied_children [0:48];       // List of tied children
    logic [5:0]  final_selection;
    
    // State encoding
    localparam IDLE = 3'b000;
    localparam FIND_MAXIMUM = 3'b001;
    localparam FIND_TIES = 3'b010;
    localparam BREAK_TIE = 3'b011;
    localparam COMPLETE = 3'b100;
    
    // Tie-breaking LFSR for random selection
    logic [15:0] lfsr_state;
    logic [5:0]  random_tie_index;
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            search_counter <= '0;
            current_child <= '0;
            current_max_ucb1 <= '0;
            current_best_child <= '0;
            current_second_best <= '0;
            tie_count <= '0;
            final_selection <= '0;
            lfsr_state <= 16'h1;
            // Initialize tied children array
            for (int i = 0; i < 49; i++) begin
                tied_children[i] <= '0;
            end
        end else begin
            state <= next_state;
            
            case (state)
                FIND_MAXIMUM: begin
                    if (search_counter < num_children && search_counter < 49) begin
                        if (ucb1_values[search_counter] > current_max_ucb1) begin
                            current_second_best <= current_best_child;
                            current_best_child <= search_counter;
                            current_max_ucb1 <= ucb1_values[search_counter];
                        end else if (ucb1_values[search_counter] > ucb1_values[current_second_best] &&
                                   search_counter != current_best_child) begin
                            current_second_best <= search_counter;
                        end
                        search_counter <= search_counter + 1;
                    end
                end
                
                FIND_TIES: begin
                    tie_count <= '0;
                    search_counter <= '0;
                    // Reset tied children list
                    for (int i = 0; i < 49; i++) begin
                        tied_children[i] <= '0;
                    end
                    
                    // Find all children with maximum UCB1 value
                    for (int j = 0; j < 49; j++) begin
                        if (j < num_children && ucb1_values[j] == current_max_ucb1) begin
                            tied_children[tie_count] <= j[5:0];
                            tie_count <= tie_count + 1;
                        end
                    end
                end
                
                BREAK_TIE: begin
                    if (tie_count > 1) begin
                        // Use LFSR for random tie-breaking
                        lfsr_state <= {lfsr_state[14:0], lfsr_state[15] ^ lfsr_state[13] ^ 
                                      lfsr_state[12] ^ lfsr_state[10]};
                        random_tie_index <= (lfsr_state ^ tie_break_seed) % tie_count;
                        final_selection <= tied_children[random_tie_index];
                    end else begin
                        final_selection <= current_best_child;
                    end
                end
                
                IDLE: begin
                    search_counter <= '0;
                    current_max_ucb1 <= '0;
                    tie_count <= '0;
                    lfsr_state <= tie_break_seed; // Seed LFSR
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
                    next_state = FIND_MAXIMUM;
            end
            
            FIND_MAXIMUM: begin
                if (search_counter >= num_children || search_counter >= 49)
                    next_state = FIND_TIES;
            end
            
            FIND_TIES:
                next_state = BREAK_TIE;
                
            BREAK_TIE:
                next_state = COMPLETE;
                
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // Selection validation
    logic selection_bounds_valid;
    always_comb begin
        selection_bounds_valid = (final_selection < num_children) && (final_selection < 49);
    end
    
    // Output assignments
    assign selected_child = final_selection;
    assign selected_ucb1 = (selection_bounds_valid) ? ucb1_values[final_selection] : 16'h0;
    assign selection_valid = (state == COMPLETE) && selection_bounds_valid;
    assign selection_complete = (state == COMPLETE);
    assign num_tied_children = tie_count;
    assign second_best_child = current_second_best;
    assign max_ucb1_value = current_max_ucb1;

endmodule
