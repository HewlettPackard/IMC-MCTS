// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// IMC-MCTS Selection Unit - Children Address Generator
// 5x5 Board Configuration
// Generates memory addresses for up to 25 child nodes with advanced addressing

module children_address_gen_5x5 #(
    parameter NUM_CHILDREN = 25,
    parameter PARENT_ADDR_WIDTH = 18,
    parameter CHILD_ADDR_WIDTH = 18,
    parameter HASH_WIDTH = 24,
    parameter DEPTH_WIDTH = 6
)(
    input  logic                                clk,
    input  logic                                rst_n,
    
    // Control Interface
    input  logic                                generate_enable,
    input  logic [PARENT_ADDR_WIDTH-1:0]       parent_address,
    input  logic [24:0]                        valid_children_mask,
    input  logic [2:0]                         addressing_mode,
    
    // Board State Interface
    input  logic [24:0] [1:0]                  board_state,
    input  logic [DEPTH_WIDTH-1:0]             current_depth,
    input  logic [HASH_WIDTH-1:0]              parent_hash,
    
    // Memory Layout Interface
    input  logic [CHILD_ADDR_WIDTH-1:0]        base_child_address,
    input  logic [2:0]                         memory_bank_select,
    input  logic                                hierarchical_enable,
    
    // Output Interface
    output logic [24:0] [CHILD_ADDR_WIDTH-1:0] child_addresses,
    output logic [24:0]                        address_valid,
    output logic                                generation_complete,
    output logic [4:0]                         valid_child_count,
    output logic [7:0] [3:0]                   bank_distribution
);

    // Internal signals
    logic [24:0] [HASH_WIDTH-1:0] child_hashes;
    logic [24:0] [4:0] child_positions;
    logic [4:0] child_counter;
    logic [2:0] generation_stage;
    
    // Position encoding for 5x5 board (row, col)
    always_comb begin
        for (int i = 0; i < 25; i++) begin
            child_positions[i] = i[4:0]; // Direct encoding: 0-24
        end
    end
    
    // Enhanced hash generation for each potential child
    genvar i;
    generate
        for (i = 0; i < NUM_CHILDREN; i++) begin : gen_child_hash
            always_comb begin
                child_hashes[i] = parent_hash ^ 
                                 ({HASH_WIDTH{1'b0}} | child_positions[i]) ^
                                 ({HASH_WIDTH{1'b0}} | current_depth) ^
                                 ({HASH_WIDTH{1'b0}} | board_state[i]) ^
                                 ({HASH_WIDTH{1'b0}} | i[7:0]); // Position-specific salt
            end
        end
    endgenerate
    
    // Multi-stage address generation
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            generation_stage <= 3'h0;
        end else if (generate_enable) begin
            if (generation_stage < 3'h4) begin
                generation_stage <= generation_stage + 1'b1;
            end else begin
                generation_stage <= 3'h0;
            end
        end else begin
            generation_stage <= 3'h0;
        end
    end
    
    // Address generation based on mode (pipelined for 25 children)
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            child_addresses <= '0;
        end else if (generation_stage == 3'h2) begin
            for (int j = 0; j < NUM_CHILDREN; j++) begin
                case (addressing_mode)
                    3'b000: begin // Direct addressing
                        child_addresses[j] <= base_child_address + 
                                           (parent_address << 5) + j[CHILD_ADDR_WIDTH-1:0];
                    end
                    
                    3'b001: begin // Hash-based addressing
                        child_addresses[j] <= base_child_address + 
                                           child_hashes[j][CHILD_ADDR_WIDTH-1:0];
                    end
                    
                    3'b010: begin // Bank-interleaved addressing
                        child_addresses[j] <= base_child_address + 
                                           (child_hashes[j][CHILD_ADDR_WIDTH-4:0] << 3) +
                                           (j % 8); // 8 banks
                    end
                    
                    3'b011: begin // Hierarchical addressing
                        if (hierarchical_enable) begin
                            child_addresses[j] <= base_child_address + 
                                               (current_depth << 10) +
                                               (parent_address[9:0]) +
                                               j[CHILD_ADDR_WIDTH-1:0];
                        end else begin
                            child_addresses[j] <= base_child_address + j[CHILD_ADDR_WIDTH-1:0];
                        end
                    end
                    
                    3'b100: begin // Compressed addressing
                        child_addresses[j] <= base_child_address + 
                                           ((parent_address & {{(CHILD_ADDR_WIDTH-10){1'b1}}, 10'h000}) | 
                                            child_hashes[j][9:0]);
                    end
                    
                    default: begin // Fallback to direct
                        child_addresses[j] <= base_child_address + j[CHILD_ADDR_WIDTH-1:0];
                    end
                endcase
            end
        end
    end
    
    // Valid child counter and bank distribution
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            child_counter <= 5'h0;
            bank_distribution <= '0;
        end else if (generation_stage == 3'h3) begin
            child_counter <= 5'h0;
            bank_distribution <= '0;
            
            for (int k = 0; k < NUM_CHILDREN; k++) begin
                if (valid_children_mask[k]) begin
                    child_counter <= child_counter + 1'b1;
                    
                    // Calculate bank distribution
                    logic [2:0] bank_idx;
                    bank_idx = child_addresses[k][2:0]; // Lower 3 bits for bank
                    bank_distribution[bank_idx] <= bank_distribution[bank_idx] + 1'b1;
                end
            end
        end
    end
    
    // Address validation and completion
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            address_valid <= 25'h0;
            generation_complete <= 1'b0;
            valid_child_count <= 5'h0;
        end else if (generation_stage == 3'h4) begin
            address_valid <= valid_children_mask;
            generation_complete <= 1'b1;
            valid_child_count <= child_counter;
        end else if (generation_stage == 3'h0) begin
            generation_complete <= 1'b0;
        end
    end

endmodule
