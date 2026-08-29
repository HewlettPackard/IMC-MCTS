// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Best Child Selector for 5x5 Go Board  
// Compares UCB1 values and selects the child with highest value
// Handles 4 children per node with pipelined comparison

module best_child_selector_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [31:0] ucb1_child0,        // UCB1 values for each child
    input  logic [31:0] ucb1_child1,
    input  logic [31:0] ucb1_child2, 
    input  logic [31:0] ucb1_child3,
    input  logic        ucb1_valid0,        // Valid flags for each UCB1 calculation
    input  logic        ucb1_valid1,
    input  logic        ucb1_valid2,
    input  logic        ucb1_valid3,
    output logic [1:0]  best_child_index,   // Index of selected child (0-3)
    output logic [31:0] best_ucb1_value,    // UCB1 value of selected child
    output logic        selection_valid,
    output logic        selection_complete
);

    // Internal registers
    logic [2:0]  state, next_state;
    logic [31:0] max_ucb1;
    logic [1:0]  max_index;
    logic [31:0] comp_val0, comp_val1;      // Comparison intermediate values
    logic [1:0]  comp_idx0, comp_idx1;      // Comparison intermediate indices
    
    // State encoding
    localparam IDLE = 3'b000;
    localparam WAIT_VALID = 3'b001;
    localparam COMPARE_01 = 3'b010;
    localparam COMPARE_23 = 3'b011;
    localparam FINAL_COMPARE = 3'b100;
    localparam COMPLETE = 3'b101;
    
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
            IDLE: if (enable) next_state = WAIT_VALID;
            WAIT_VALID: if (ucb1_valid0 && ucb1_valid1 && ucb1_valid2 && ucb1_valid3) 
                           next_state = COMPARE_01;
            COMPARE_01: next_state = COMPARE_23;
            COMPARE_23: next_state = FINAL_COMPARE;
            FINAL_COMPARE: next_state = COMPLETE;
            COMPLETE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end
    
    // Pipelined comparison logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            comp_val0 <= '0;
            comp_val1 <= '0;
            comp_idx0 <= '0;
            comp_idx1 <= '0;
            max_ucb1 <= '0;
            max_index <= '0;
        end else begin
            case (state)
                COMPARE_01: begin
                    // Compare children 0 and 1
                    if (ucb1_child0 >= ucb1_child1) begin
                        comp_val0 <= ucb1_child0;
                        comp_idx0 <= 2'b00;
                    end else begin
                        comp_val0 <= ucb1_child1;
                        comp_idx0 <= 2'b01;
                    end
                end
                
                COMPARE_23: begin
                    // Compare children 2 and 3
                    if (ucb1_child2 >= ucb1_child3) begin
                        comp_val1 <= ucb1_child2;
                        comp_idx1 <= 2'b10;
                    end else begin
                        comp_val1 <= ucb1_child3;
                        comp_idx1 <= 2'b11;
                    end
                end
                
                FINAL_COMPARE: begin
                    // Final comparison between winners of previous comparisons
                    if (comp_val0 >= comp_val1) begin
                        max_ucb1 <= comp_val0;
                        max_index <= comp_idx0;
                    end else begin
                        max_ucb1 <= comp_val1;
                        max_index <= comp_idx1;
                    end
                end
            endcase
        end
    end
    
    // Handle tie-breaking (prefer lower index for deterministic behavior)
    logic [31:0] ucb1_values [0:3];
    logic [1:0] tie_break_index;
    
    assign ucb1_values[0] = ucb1_child0;
    assign ucb1_values[1] = ucb1_child1;
    assign ucb1_values[2] = ucb1_child2;
    assign ucb1_values[3] = ucb1_child3;
    
    // Tie-breaking logic: if multiple children have same UCB1, select lowest index
    always_comb begin
        tie_break_index = max_index;
        for (int i = 0; i < 4; i++) begin
            if (ucb1_values[i] == max_ucb1 && i < max_index) begin
                tie_break_index = i[1:0];
            end
        end
    end
    
    // Output assignments
    assign best_child_index = (state == COMPLETE) ? tie_break_index : '0;
    assign best_ucb1_value = (state == COMPLETE) ? max_ucb1 : '0;
    assign selection_valid = (state == COMPLETE);
    assign selection_complete = (state == COMPLETE);
    
    // Additional logic for handling unvisited children
    // Unvisited children (UCB1 = 0xFFFFFFFF) should be prioritized
    logic has_unvisited;
    logic [1:0] first_unvisited_index;
    
    always_comb begin
        has_unvisited = 1'b0;
        first_unvisited_index = 2'b00;
        
        // Check for unvisited children in order
        if (ucb1_child0 == 32'hFFFFFFFF) begin
            has_unvisited = 1'b1;
            first_unvisited_index = 2'b00;
        end else if (ucb1_child1 == 32'hFFFFFFFF) begin
            has_unvisited = 1'b1;
            first_unvisited_index = 2'b01;
        end else if (ucb1_child2 == 32'hFFFFFFFF) begin
            has_unvisited = 1'b1;
            first_unvisited_index = 2'b10;
        end else if (ucb1_child3 == 32'hFFFFFFFF) begin
            has_unvisited = 1'b1;
            first_unvisited_index = 2'b11;
        end
    end
    
    // Override selection if unvisited children exist
    logic [1:0] final_selection;
    logic [31:0] final_ucb1;
    
    assign final_selection = has_unvisited ? first_unvisited_index : tie_break_index;
    assign final_ucb1 = has_unvisited ? 32'hFFFFFFFF : max_ucb1;
    
    // Final output override
    assign best_child_index = (state == COMPLETE) ? final_selection : '0;
    assign best_ucb1_value = (state == COMPLETE) ? final_ucb1 : '0;
    
endmodule
