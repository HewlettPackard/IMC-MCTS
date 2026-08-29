// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Path Address Extractor for 7x7 Go Board
// Manages address sequences for MCTS tree traversal during backpropagation
// Supports variable-depth paths with stack-based storage for 7x7 complexity

module path_address_extractor_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        path_push,           // Add address to path during selection/expansion
    input  logic        path_pop,            // Retrieve next address during backpropagation
    input  logic [15:0] node_address_in,     // Input node address to add to path
    input  logic        path_reset,          // Clear path for new simulation
    input  logic        backprop_start,      // Begin backpropagation traversal
    input  logic [5:0]  max_depth,           // Maximum expected path depth
    output logic [15:0] current_address,     // Current node address for backpropagation update
    output logic [5:0]  path_depth,          // Current depth of stored path
    output logic        path_valid,          // Validity flag for current address
    output logic        path_empty,          // Flag indicating path traversal complete
    output logic [15:0] next_address,        // Preview of next address in sequence
    output logic [15:0] address_sequence [0:31], // 32-level deep address stack
    output logic        stack_overflow       // Error flag for path depth overflow
);

    // Internal registers
    logic [2:0]  state, next_state;
    logic [5:0]  stack_pointer;              // Current position in address stack
    logic [5:0]  depth_counter;
    logic [15:0] address_stack [0:31];       // Stack for 32-level deep paths
    logic [15:0] current_addr_reg;
    logic        overflow_detected;
    logic        underflow_detected;
    
    // State encoding
    localparam IDLE = 3'b000;
    localparam PUSH_ADDRESS = 3'b001;
    localparam POP_ADDRESS = 3'b010;
    localparam UPDATE_DEPTH = 3'b011;
    localparam CHECK_BOUNDS = 3'b100;
    localparam COMPLETE = 3'b101;
    
    // Stack management parameters
    localparam MAX_STACK_DEPTH = 6'd32;      // Maximum stack depth for 7x7 complexity
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            stack_pointer <= '0;
            depth_counter <= '0;
            current_addr_reg <= '0;
            overflow_detected <= 1'b0;
            underflow_detected <= 1'b0;
            // Initialize address stack
            for (int i = 0; i < 32; i++) begin
                address_stack[i] <= '0;
            end
        end else begin
            state <= next_state;
            
            case (state)
                PUSH_ADDRESS: begin
                    if (stack_pointer < MAX_STACK_DEPTH && !overflow_detected) begin
                        address_stack[stack_pointer] <= node_address_in;
                        stack_pointer <= stack_pointer + 1;
                        depth_counter <= depth_counter + 1;
                    end else begin
                        overflow_detected <= 1'b1;
                    end
                end
                
                POP_ADDRESS: begin
                    if (stack_pointer > 0 && !underflow_detected) begin
                        stack_pointer <= stack_pointer - 1;
                        current_addr_reg <= address_stack[stack_pointer - 1];
                        depth_counter <= depth_counter - 1;
                    end else begin
                        underflow_detected <= 1'b1;
                        current_addr_reg <= '0;
                    end
                end
                
                UPDATE_DEPTH: begin
                    // Update depth information and validate stack state
                    if (depth_counter != stack_pointer) begin
                        depth_counter <= stack_pointer;
                    end
                end
                
                CHECK_BOUNDS: begin
                    // Bounds checking and error detection
                    if (stack_pointer > MAX_STACK_DEPTH) begin
                        overflow_detected <= 1'b1;
                        stack_pointer <= MAX_STACK_DEPTH;
                    end
                    
                    if (depth_counter > max_depth && max_depth != 0) begin
                        // Depth exceeds expected maximum
                        overflow_detected <= 1'b1;
                    end
                end
                
                IDLE: begin
                    if (path_reset) begin
                        stack_pointer <= '0;
                        depth_counter <= '0;
                        current_addr_reg <= '0;
                        overflow_detected <= 1'b0;
                        underflow_detected <= 1'b0;
                        // Clear address stack
                        for (int j = 0; j < 32; j++) begin
                            address_stack[j] <= '0;
                        end
                    end
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        
        case (state)
            IDLE: begin
                if (path_push)
                    next_state = PUSH_ADDRESS;
                else if (path_pop)
                    next_state = POP_ADDRESS;
            end
            
            PUSH_ADDRESS:
                next_state = UPDATE_DEPTH;
                
            POP_ADDRESS:
                next_state = UPDATE_DEPTH;
                
            UPDATE_DEPTH:
                next_state = CHECK_BOUNDS;
                
            CHECK_BOUNDS:
                next_state = COMPLETE;
                
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // Stack peek operations (combinatorial)
    logic [15:0] peek_next_address;
    always_comb begin
        if (stack_pointer > 1) begin
            peek_next_address = address_stack[stack_pointer - 2];
        end else begin
            peek_next_address = '0;
        end
    end
    
    // Path validation logic
    logic path_state_valid;
    always_comb begin
        path_state_valid = !overflow_detected && 
                          !underflow_detected && 
                          (stack_pointer <= MAX_STACK_DEPTH) &&
                          (state == COMPLETE || state == IDLE);
    end
    
    // Stack status monitoring
    logic stack_nearly_full;
    logic stack_nearly_empty;
    always_comb begin
        stack_nearly_full = (stack_pointer >= MAX_STACK_DEPTH - 2);
        stack_nearly_empty = (stack_pointer <= 2);
    end
    
    // Output assignments
    assign current_address = current_addr_reg;
    assign path_depth = depth_counter;
    assign path_valid = path_state_valid && (current_addr_reg != '0);
    assign path_empty = (stack_pointer == 0) || underflow_detected;
    assign next_address = peek_next_address;
    assign stack_overflow = overflow_detected;
    
    // Copy address stack to output array
    genvar k;
    generate
        for (k = 0; k < 32; k++) begin : addr_stack_assign
            assign address_sequence[k] = address_stack[k];
        end
    endgenerate

endmodule
