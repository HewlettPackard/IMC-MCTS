// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Backpropagation Unit - Path Address Extractor
// 2x2 Board Accelerator Architecture
// ============================================================================

module path_address_extractor (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [11:0] selection_path,  // 3x4-bit addresses
    input  logic [1:0]  path_depth,     // 1-3 nodes
    input  logic        path_valid,
    
    output logic [3:0]  node_addr_0,
    output logic [3:0]  node_addr_1,
    output logic [3:0]  node_addr_2,
    output logic [2:0]  addr_valid,
    output logic        extraction_done
);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            node_addr_0     <= 4'h0;
            node_addr_1     <= 4'h0;
            node_addr_2     <= 4'h0;
            addr_valid      <= 3'h0;
            extraction_done <= 1'b0;
        end else if (enable && path_valid) begin
            // Unpack selection path into individual addresses
            node_addr_0 <= selection_path[3:0];   // Root node
            node_addr_1 <= selection_path[7:4];   // Intermediate node
            node_addr_2 <= selection_path[11:8];  // Leaf node
            
            // Generate validity mask based on path depth
            case (path_depth)
                2'h1: addr_valid <= 3'b001; // Only root valid
                2'h2: addr_valid <= 3'b011; // Root + intermediate valid
                2'h3: addr_valid <= 3'b111; // All nodes valid
                default: addr_valid <= 3'b000;
            endcase
            
            extraction_done <= 1'b1;
        end else begin
            extraction_done <= 1'b0;
        end
    end

endmodule
