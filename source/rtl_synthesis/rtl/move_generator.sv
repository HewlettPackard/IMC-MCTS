// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Expansion Unit - Move Generator
// 2x2 Board Accelerator Architecture
// ============================================================================

module move_generator (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    input  logic [3:0] empty_mask,
    input  logic       current_player,
    
    output logic [1:0] move_0_coord,
    output logic [1:0] move_1_coord,
    output logic [1:0] move_2_coord,
    output logic [1:0] move_3_coord,
    output logic [3:0] move_valid,
    output logic [2:0] move_count
);

    // Convert position index to 2D coordinates
    // Position 0: (0,0) = 2'b00
    // Position 1: (0,1) = 2'b01  
    // Position 2: (1,0) = 2'b10
    // Position 3: (1,1) = 2'b11
    function automatic logic [1:0] pos_to_coord(logic [1:0] pos_idx);
        case (pos_idx)
            2'h0: return 2'b00; // (0,0)
            2'h1: return 2'b01; // (0,1)
            2'h2: return 2'b10; // (1,0)
            2'h3: return 2'b11; // (1,1)
            default: return 2'b00;
        endcase
    endfunction

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            move_0_coord <= 2'h0;
            move_1_coord <= 2'h0;
            move_2_coord <= 2'h0;
            move_3_coord <= 2'h0;
            move_valid   <= 4'h0;
            move_count   <= 3'h0;
        end else if (enable) begin
            // Generate move coordinates for empty positions
            move_0_coord <= pos_to_coord(2'h0);
            move_1_coord <= pos_to_coord(2'h1);
            move_2_coord <= pos_to_coord(2'h2);
            move_3_coord <= pos_to_coord(2'h3);
            
            // Valid moves correspond to empty positions
            move_valid <= empty_mask;
            
            // Count valid moves
            move_count <= empty_mask[0] + empty_mask[1] + empty_mask[2] + empty_mask[3];
        end
    end

endmodule
