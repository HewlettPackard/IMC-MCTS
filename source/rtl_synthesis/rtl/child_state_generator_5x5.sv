// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Child State Generator for 5x5 Go Board
// Generates new board states for child nodes by applying moves
// Handles 25 positions with proper move validation and state updates

module child_state_generator_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [49:0] parent_board_state,  // Current 5x5 board state (50 bits, 2 bits per position)
    input  logic        current_player,      // 0=black, 1=white
    input  logic [4:0]  move_position,       // Position to place stone (0-24)
    input  logic        move_valid,          // Move validation signal
    output logic [49:0] child_board_state,   // New board state after move (50 bits, 2 bits per position)
    output logic        child_player,        // Next player's turn
    output logic        state_valid,
    output logic        generation_complete
);

    // Internal registers
    logic [2:0]  state, next_state;
    logic [24:0] new_board;
    logic [24:0] temp_board;
    logic        next_player;
    logic [4:0]  move_pos_reg;
    logic        player_reg;
    
    // State encoding
    localparam IDLE = 3'b000;
    localparam VALIDATE_MOVE = 3'b001;
    localparam APPLY_MOVE = 3'b010;
    localparam CHECK_CAPTURES = 3'b011;
    localparam UPDATE_STATE = 3'b100;
    localparam COMPLETE = 3'b101;
    
    // Board position decoding for 5x5 (25 positions)
    // Each position uses 2 bits: 00=empty, 01=black, 10=white, 11=invalid
    logic [1:0] position_states [0:24];
    logic [1:0] new_position_states [0:24];
    
    // Generate array assignments for easier manipulation
    genvar i;
    generate
        for (i = 0; i < 25; i++) begin : pos_decode
            assign position_states[i] = parent_board_state[2*i+1:2*i];
            assign new_board[2*i+1:2*i] = new_position_states[i];
        end
    endgenerate
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            move_pos_reg <= '0;
            player_reg <= 1'b0;
        end else begin
            state <= next_state;
            if (enable && state == IDLE) begin
                move_pos_reg <= move_position;
                player_reg <= current_player;
            end
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        case (state)
            IDLE: if (enable) next_state = VALIDATE_MOVE;
            VALIDATE_MOVE: next_state = move_valid ? APPLY_MOVE : COMPLETE;
            APPLY_MOVE: next_state = CHECK_CAPTURES;
            CHECK_CAPTURES: next_state = UPDATE_STATE;
            UPDATE_STATE: next_state = COMPLETE;
            COMPLETE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end
    
    // Move application logic
    always_comb begin
        // Default: copy parent board
        for (int j = 0; j < 25; j++) begin
            new_position_states[j] = position_states[j];
        end
        
        // Apply move if in APPLY_MOVE state
        if (state == APPLY_MOVE && move_pos_reg < 25) begin
            // Place stone for current player
            new_position_states[move_pos_reg] = player_reg ? 2'b10 : 2'b01;
        end
        
        // Handle captures in CHECK_CAPTURES state
        if (state == CHECK_CAPTURES) begin
            // Simple capture logic for 5x5 board
            // Check adjacent positions for opponent groups without liberties
            for (int k = 0; k < 25; k++) begin
                if (is_captured(k, new_position_states, ~player_reg)) begin
                    new_position_states[k] = 2'b00; // Remove captured stone
                end
            end
        end
    end
    
    // Helper function to check if a position is captured
    function logic is_captured(input int pos, input logic [1:0] board [0:24], input logic opponent);
        logic [1:0] stone_color;
        logic has_liberty;
        int row, col;
        
        stone_color = opponent ? 2'b10 : 2'b01;
        has_liberty = 1'b0;
        
        // Check if position has opponent stone
        if (board[pos] != stone_color) begin
            return 1'b0;
        end
        
        // Convert position to row/col
        row = pos / 5;
        col = pos % 5;
        
        // Check adjacent positions for liberties
        // Up
        if (row > 0 && board[pos-5] == 2'b00) has_liberty = 1'b1;
        // Down  
        if (row < 4 && board[pos+5] == 2'b00) has_liberty = 1'b1;
        // Left
        if (col > 0 && board[pos-1] == 2'b00) has_liberty = 1'b1;
        // Right
        if (col < 4 && board[pos+1] == 2'b00) has_liberty = 1'b1;
        
        return !has_liberty;
    endfunction
    
    // Output registers
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            temp_board <= '0;
            next_player <= 1'b0;
        end else if (state == UPDATE_STATE) begin
            temp_board <= new_board;
            next_player <= ~player_reg; // Switch players
        end
    end
    
    // Output assignments
    assign child_board_state = temp_board;
    assign child_player = next_player;
    assign state_valid = (state == COMPLETE);
    assign generation_complete = (state == COMPLETE);
    
    // Additional validation
    logic move_position_valid;
    assign move_position_valid = (move_position < 25) && 
                                (position_states[move_position] == 2'b00);
    
    // Error handling for invalid moves
    logic generation_error;
    assign generation_error = enable && (!move_position_valid || !move_valid);
    
endmodule
