// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Children Address Generator for 7x7 Go Board
// Generates memory addresses for child nodes in MCTS tree
// Supports up to 49 children per node for 7x7 board positions

module children_address_gen_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [15:0] parent_address,      // 16-bit parent node address
    input  logic [5:0]  child_index,        // Child index (0-48 for 7x7 board)
    input  logic [5:0]  num_children,       // Total number of children
    input  logic        generate_all,       // Generate addresses for all children
    output logic [15:0] child_address,      // Generated child address
    output logic [15:0] child_addresses [0:48], // All child addresses (7x7 = 49 max)
    output logic        address_valid,
    output logic        generation_complete,
    output logic        addresses_ready
);

    // Internal registers
    logic [2:0]  state, next_state;
    logic [5:0]  current_index;
    logic [15:0] base_address;
    logic [15:0] address_buffer [0:48];      // Buffer for 49 addresses (7x7 board)
    logic [5:0]  generation_counter;
    
    // State encoding
    localparam IDLE = 3'b000;
    localparam CALCULATE_BASE = 3'b001;
    localparam GENERATE_SINGLE = 3'b010;
    localparam GENERATE_ALL_CHILDREN = 3'b011;
    localparam COMPLETE = 3'b100;
    
    // Address calculation constants for 7x7 tree structure
    localparam [15:0] CHILDREN_PER_NODE = 16'd49;    // Maximum children for 7x7
    localparam [15:0] NODE_SIZE = 16'd4;             // Address increment per node
    localparam [15:0] TREE_LEVEL_OFFSET = 16'd2048; // Offset between tree levels
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            current_index <= '0;
            generation_counter <= '0;
            base_address <= '0;
            // Initialize address buffer
            for (int i = 0; i < 49; i++) begin
                address_buffer[i] <= '0;
            end
        end else begin
            state <= next_state;
            
            case (state)
                CALCULATE_BASE: begin
                    base_address <= parent_address + TREE_LEVEL_OFFSET;
                    current_index <= child_index;
                    generation_counter <= '0;
                end
                
                GENERATE_SINGLE: begin
                    address_buffer[current_index] <= base_address + (current_index * NODE_SIZE);
                end
                
                GENERATE_ALL_CHILDREN: begin
                    if (generation_counter < num_children && generation_counter < 49) begin
                        address_buffer[generation_counter] <= base_address + (generation_counter * NODE_SIZE);
                        generation_counter <= generation_counter + 1;
                    end
                end
                
                IDLE: begin
                    generation_counter <= '0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        
        case (state)
            IDLE: begin
                if (enable) begin
                    next_state = CALCULATE_BASE;
                end
            end
            
            CALCULATE_BASE: begin
                if (generate_all)
                    next_state = GENERATE_ALL_CHILDREN;
                else
                    next_state = GENERATE_SINGLE;
            end
            
            GENERATE_SINGLE:
                next_state = COMPLETE;
                
            GENERATE_ALL_CHILDREN: begin
                if (generation_counter >= num_children || generation_counter >= 49)
                    next_state = COMPLETE;
            end
            
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // Address validation for 7x7 constraints
    logic address_in_bounds;
    always_comb begin
        address_in_bounds = (child_index < 49) && (child_index < num_children);
    end
    
    // Output assignments
    assign child_address = address_buffer[current_index];
    
    // Generate output array assignment
    genvar i;
    generate
        for (i = 0; i < 49; i++) begin : addr_assign
            assign child_addresses[i] = address_buffer[i];
        end
    endgenerate
    
    assign address_valid = (state == COMPLETE) && address_in_bounds;
    assign generation_complete = (state == COMPLETE);
    assign addresses_ready = (state == COMPLETE) && generate_all;

endmodule
