// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Expansion Unit - Player Turn Logic
// 2x2 Board Accelerator Architecture
// ============================================================================

module player_turn_logic (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    input  logic [1:0] position_0,
    input  logic [1:0] position_1,
    input  logic [1:0] position_2,
    input  logic [1:0] position_3,
    
    output logic       current_player,
    output logic [2:0] move_count,
    output logic       turn_valid
);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_player <= 1'b0;  // Player 1 starts
            move_count     <= 3'h0;
            turn_valid     <= 1'b0;
        end else if (enable) begin
            // Count occupied positions (non-zero states)
            move_count <= (position_0 != 2'b00) + 
                         (position_1 != 2'b00) + 
                         (position_2 != 2'b00) + 
                         (position_3 != 2'b00);
            
            // Current player based on move count parity
            // Even count = Player 1 (0), Odd count = Player 2 (1)
            current_player <= move_count[0];
            
            turn_valid <= 1'b1;
        end else begin
            turn_valid <= 1'b0;
        end
    end

endmodule
