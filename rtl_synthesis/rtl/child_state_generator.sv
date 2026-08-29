// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Expansion Unit - Child State Generator
// 2x2 Board Accelerator Architecture
// ============================================================================

module child_state_generator (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    input  logic [7:0] current_state,  // 4x2-bit positions
    input  logic [1:0] move_0_coord,
    input  logic [1:0] move_1_coord,
    input  logic [1:0] move_2_coord,
    input  logic [1:0] move_3_coord,
    input  logic [3:0] move_valid,
    input  logic       current_player,
    
    output logic [7:0] child_state_0,
    output logic [7:0] child_state_1,
    output logic [7:0] child_state_2,
    output logic [7:0] child_state_3,
    output logic [3:0] child_valid
);

    // Convert 2D coordinate to position index
    function automatic logic [1:0] coord_to_pos(logic [1:0] coord);
        case (coord)
            2'b00: return 2'h0; // (0,0) -> position 0
            2'b01: return 2'h1; // (0,1) -> position 1
            2'b10: return 2'h2; // (1,0) -> position 2
            2'b11: return 2'h3; // (1,1) -> position 3
            default: return 2'h0;
        endcase
    endfunction

    // Apply move to board state
    function automatic logic [7:0] apply_move(
        logic [7:0] state, 
        logic [1:0] coord, 
        logic player
    );
        logic [1:0] pos_idx;
        logic [7:0] new_state;
        logic [1:0] player_encoding;
        
        pos_idx = coord_to_pos(coord);
        player_encoding = player ? 2'b10 : 2'b01;  // Player 1=01, Player 2=10
        new_state = state;
        
        case (pos_idx)
            2'h0: new_state[1:0]  = player_encoding;
            2'h1: new_state[3:2]  = player_encoding;
            2'h2: new_state[5:4]  = player_encoding;
            2'h3: new_state[7:6]  = player_encoding;
        endcase
        
        return new_state;
    endfunction

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            child_state_0 <= 8'h0;
            child_state_1 <= 8'h0;
            child_state_2 <= 8'h0;
            child_state_3 <= 8'h0;
            child_valid   <= 4'h0;
        end else if (enable) begin
            // Generate child states by applying moves
            child_state_0 <= move_valid[0] ? 
                apply_move(current_state, move_0_coord, current_player) : current_state;
            child_state_1 <= move_valid[1] ? 
                apply_move(current_state, move_1_coord, current_player) : current_state;
            child_state_2 <= move_valid[2] ? 
                apply_move(current_state, move_2_coord, current_player) : current_state;
            child_state_3 <= move_valid[3] ? 
                apply_move(current_state, move_3_coord, current_player) : current_state;
            
            child_valid <= move_valid;
        end else begin
            child_valid <= 4'h0;
        end
    end

endmodule
