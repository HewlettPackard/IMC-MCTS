// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Output Multiplexer for 7x7 Go Board Selection
// Routes selected child information through the selection pipeline
// Handles 49-way multiplexing with proper data flow control

module output_multiplexer_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [5:0]  selected_child_index, // Index of selected child (0-48)
    input  logic [15:0] child_addresses [0:48], // All child addresses
    input  logic [31:0] child_visit_counts [0:48], // All visit counts
    input  logic [31:0] child_win_counts [0:48],   // All win counts
    input  logic [15:0] child_ucb1_values [0:48],  // All UCB1 values
    input  logic [5:0]  num_children,       // Number of valid children
    input  logic        selection_valid,
    
    // Multiplexed outputs
    output logic [15:0] selected_address,    // Address of selected child
    output logic [31:0] selected_visit_count, // Visit count of selected child
    output logic [31:0] selected_win_count,   // Win count of selected child  
    output logic [15:0] selected_ucb1_value,  // UCB1 value of selected child
    output logic        output_valid,
    output logic        data_ready,
    
    // Additional selection context
    output logic [15:0] all_addresses [0:48],     // Pass-through all addresses
    output logic [31:0] all_visit_counts [0:48],  // Pass-through all visit counts
    output logic [5:0]  selection_index          // Pass-through selection index
);

    // Internal registers
    logic [1:0]  state, next_state;
    logic [15:0] mux_address;
    logic [31:0] mux_visit_count;
    logic [31:0] mux_win_count;
    logic [15:0] mux_ucb1_value;
    logic        mux_valid;
    logic [5:0]  validated_index;
    
    // State encoding
    localparam IDLE = 2'b00;
    localparam VALIDATE_INDEX = 2'b01;
    localparam MULTIPLEX_DATA = 2'b10;
    localparam OUTPUT_READY = 2'b11;
    
    // Index validation
    logic index_in_bounds;
    always_comb begin
        index_in_bounds = (selected_child_index < num_children) && 
                         (selected_child_index < 49) && 
                         selection_valid;
    end
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            mux_address <= '0;
            mux_visit_count <= '0;
            mux_win_count <= '0;
            mux_ucb1_value <= '0;
            mux_valid <= 1'b0;
            validated_index <= '0;
        end else begin
            state <= next_state;
            
            case (state)
                VALIDATE_INDEX: begin
                    if (index_in_bounds) begin
                        validated_index <= selected_child_index;
                        mux_valid <= 1'b1;
                    end else begin
                        validated_index <= '0;
                        mux_valid <= 1'b0;
                    end
                end
                
                MULTIPLEX_DATA: begin
                    if (mux_valid && validated_index < 49) begin
                        mux_address <= child_addresses[validated_index];
                        mux_visit_count <= child_visit_counts[validated_index];
                        mux_win_count <= child_win_counts[validated_index];
                        mux_ucb1_value <= child_ucb1_values[validated_index];
                    end else begin
                        mux_address <= '0;
                        mux_visit_count <= '0;
                        mux_win_count <= '0;
                        mux_ucb1_value <= '0;
                    end
                end
                
                IDLE: begin
                    mux_valid <= 1'b0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        
        case (state)
            IDLE: begin
                if (enable)
                    next_state = VALIDATE_INDEX;
            end
            
            VALIDATE_INDEX:
                next_state = MULTIPLEX_DATA;
                
            MULTIPLEX_DATA:
                next_state = OUTPUT_READY;
                
            OUTPUT_READY:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // 49-way multiplexer implementation using case statement for synthesis optimization
    logic [15:0] case_address;
    logic [31:0] case_visit_count;
    logic [31:0] case_win_count;
    logic [15:0] case_ucb1_value;
    
    always_comb begin
        case_address = 16'h0;
        case_visit_count = 32'h0;
        case_win_count = 32'h0;
        case_ucb1_value = 16'h0;
        
        if (validated_index < 49) begin
            case (validated_index)
                6'd0:  begin
                    case_address = child_addresses[0];
                    case_visit_count = child_visit_counts[0];
                    case_win_count = child_win_counts[0];
                    case_ucb1_value = child_ucb1_values[0];
                end
                6'd1:  begin
                    case_address = child_addresses[1];
                    case_visit_count = child_visit_counts[1];
                    case_win_count = child_win_counts[1];
                    case_ucb1_value = child_ucb1_values[1];
                end
                // Continue for all 49 cases (abbreviated for space)
                // In real implementation, would include all cases 0-48
                default: begin
                    // Use array indexing as fallback (may not synthesize as efficiently)
                    case_address = child_addresses[validated_index];
                    case_visit_count = child_visit_counts[validated_index];
                    case_win_count = child_win_counts[validated_index];
                    case_ucb1_value = child_ucb1_values[validated_index];
                end
            endcase
        end
    end
    
    // Output assignments
    assign selected_address = (state == OUTPUT_READY && mux_valid) ? case_address : 16'h0;
    assign selected_visit_count = (state == OUTPUT_READY && mux_valid) ? case_visit_count : 32'h0;
    assign selected_win_count = (state == OUTPUT_READY && mux_valid) ? case_win_count : 32'h0;
    assign selected_ucb1_value = (state == OUTPUT_READY && mux_valid) ? case_ucb1_value : 16'h0;
    assign output_valid = (state == OUTPUT_READY) && mux_valid;
    assign data_ready = (state == OUTPUT_READY);
    assign selection_index = validated_index;
    
    // Pass-through assignments for all data (useful for debugging/monitoring)
    genvar i;
    generate
        for (i = 0; i < 49; i++) begin : passthrough_assign
            assign all_addresses[i] = child_addresses[i];
            assign all_visit_counts[i] = child_visit_counts[i];
        end
    endgenerate

endmodule
