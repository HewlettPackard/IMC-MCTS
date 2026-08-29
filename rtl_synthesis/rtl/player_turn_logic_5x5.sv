// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Player Turn Logic for 5x5 Go Board
// Manages turn switching and game state transitions during MCTS expansion
// Handles player alternation and special game conditions

module player_turn_logic_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic        current_player,      // 0=black, 1=white
    input  logic        move_applied,        // Signal that move was successfully applied
    input  logic        pass_move,           // Player passes their turn
    input  logic        game_over,           // Game termination signal
    input  logic [49:0] board_state,         // Current board state (50 bits, 2 bits per position)
    input  logic [4:0]  empty_count,         // Number of empty positions
    output logic        next_player,         // Player for next turn
    output logic        turn_complete,
    output logic        switch_valid,
    output logic        game_state_valid,
    
    // Game state information
    output logic        consecutive_passes,   // Both players passed
    output logic        board_full,          // No more moves available
    output logic        turn_count_overflow  // Maximum turns reached
);

    // Internal registers
    logic [2:0]  state, next_state;
    logic        player_reg;
    logic        pass_history [0:1];         // Track last 2 moves for consecutive passes
    logic [7:0]  turn_counter;               // Track total number of turns
    logic        game_end_detected;
    
    // Internal variables
    logic [3:0] pass_count;
    logic [3:0] recent_pass_count;
    
    // State encoding
    localparam IDLE = 3'b000;
    localparam CHECK_CONDITIONS = 3'b001;
    localparam SWITCH_PLAYER = 3'b010;
    localparam UPDATE_HISTORY = 3'b011;
    localparam COMPLETE = 3'b100;
    
    // Maximum turns for 5x5 board (safety limit)
    localparam MAX_TURNS = 8'd200;
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            player_reg <= 1'b0;  // Start with black
            turn_counter <= '0;
            pass_history[0] <= 1'b0;
            pass_history[1] <= 1'b0;
        end else begin
            state <= next_state;
            
            case (state)
                IDLE: begin
                    if (enable) begin
                        player_reg <= current_player;
                    end
                end
                
                UPDATE_HISTORY: begin
                    // Shift pass history and add current move
                    pass_history[1] <= pass_history[0];
                    pass_history[0] <= pass_move;
                    
                    // Increment turn counter
                    if (turn_counter < MAX_TURNS) begin
                        turn_counter <= turn_counter + 1;
                    end
                end
                
                SWITCH_PLAYER: begin
                    // Alternate players
                    player_reg <= ~player_reg;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        case (state)
            IDLE: if (enable) next_state = CHECK_CONDITIONS;
            CHECK_CONDITIONS: if (!game_end_detected) next_state = SWITCH_PLAYER;
                             else next_state = COMPLETE;
            SWITCH_PLAYER: next_state = UPDATE_HISTORY;
            UPDATE_HISTORY: next_state = COMPLETE;
            COMPLETE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end
    
    // Game ending condition detection
    always_comb begin
        game_end_detected = 1'b0;
        
        // Check for consecutive passes
        if (pass_history[0] && pass_history[1] && pass_move) begin
            game_end_detected = 1'b1;
        end
        
        // Check if board is full
        if (empty_count == 0) begin
            game_end_detected = 1'b1;
        end
        
        // Check for external game over signal
        if (game_over) begin
            game_end_detected = 1'b1;
        end
        
        // Check for maximum turns reached
        if (turn_counter >= MAX_TURNS) begin
            game_end_detected = 1'b1;
        end
    end
    
    // Turn validation logic
    logic turn_is_valid;
    always_comb begin
        turn_is_valid = 1'b1;
        
        // Invalid if game should have ended
        if (game_end_detected && !game_over) begin
            turn_is_valid = 1'b0;
        end
        
        // Invalid if no move was applied and no pass
        if (!move_applied && !pass_move && enable) begin
            turn_is_valid = 1'b0;
        end
    end
    
    // Output assignments
    assign next_player = player_reg;
    assign turn_complete = (state == COMPLETE);
    assign switch_valid = turn_is_valid && (state == COMPLETE);
    assign game_state_valid = (state == COMPLETE);
    
    // Game state flags
    assign consecutive_passes = pass_history[0] && pass_history[1];
    assign board_full = (empty_count == 0);
    assign turn_count_overflow = (turn_counter >= MAX_TURNS);
    
    // Additional game state analysis
    logic early_game, mid_game, end_game;
    
    always_comb begin
        early_game = (turn_counter < 10);
        mid_game = (turn_counter >= 10) && (turn_counter < 40);
        end_game = (turn_counter >= 40);
    end
    
    // Player statistics tracking
    logic [6:0] black_moves, white_moves;
    logic [6:0] black_passes, white_passes;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            black_moves <= '0;
            white_moves <= '0;
            black_passes <= '0;
            white_passes <= '0;
        end else if (state == UPDATE_HISTORY) begin
            if (current_player == 1'b0) begin // Black's turn
                if (pass_move) begin
                    black_passes <= black_passes + 1;
                end else if (move_applied) begin
                    black_moves <= black_moves + 1;
                end
            end else begin // White's turn
                if (pass_move) begin
                    white_passes <= white_passes + 1;
                end else if (move_applied) begin
                    white_moves <= white_moves + 1;
                end
            end
        end
    end
    
    // Turn history for advanced game analysis
    logic [1:0] recent_moves [0:7];  // Track last 8 moves
    logic [2:0] history_index;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < 8; i++) begin
                recent_moves[i] <= 2'b00;
            end
            history_index <= '0;
        end else if (state == UPDATE_HISTORY) begin
            recent_moves[history_index] <= {pass_move, current_player};
            history_index <= (history_index == 7) ? 3'b000 : history_index + 1;
        end
    end
    
    // Pattern detection for move validation
    logic alternating_pattern;
    logic excessive_passing;
    
    always_comb begin
        alternating_pattern = 1'b1;
        excessive_passing = 1'b0;
        
        // Check if players are properly alternating
        for (int j = 1; j < 8; j++) begin
            if (recent_moves[j][0] != recent_moves[j-1][0]) begin
                alternating_pattern = 1'b0;
            end
        end
        
        // Check for excessive passing (more than 4 passes in last 8 moves)
        pass_count = 0;
        for (int k = 0; k < 8; k++) begin
            if (recent_moves[k][1]) pass_count++;
        end
        excessive_passing = (pass_count > 4);
    end
    
    // Debug and verification outputs
    logic [7:0] debug_turn_count;
    logic [1:0] debug_game_phase;
    
    assign debug_turn_count = turn_counter;
    assign debug_game_phase = early_game ? 2'b00 : (mid_game ? 2'b01 : 2'b10);
    
endmodule
