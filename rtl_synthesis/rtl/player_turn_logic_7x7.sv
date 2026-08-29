// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Player Turn Logic for 7x7 Go Board
// Manages turn switching and game state transitions during MCTS expansion
// Handles player alternation and special game conditions for 49-position board

module player_turn_logic_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic        current_player,      // 0=black, 1=white
    input  logic        move_applied,        // Signal that move was successfully applied
    input  logic        pass_move,           // Player passes their turn
    input  logic        game_over,           // Game termination signal
    input  logic [97:0] board_state,         // Current board state (98 bits, 2 bits per position)
    input  logic [5:0]  empty_count,         // Number of empty positions
    output logic        next_player,         // Player for next turn
    output logic        turn_complete,
    output logic        switch_valid,
    output logic        game_state_valid,
    
    // Game state information
    output logic [7:0]  turn_counter,        // Total number of turns played
    output logic        consecutive_passes,   // Two consecutive passes detected
    output logic        board_full,          // No empty positions remaining
    output logic        game_end_condition   // Game should end
);

    // Internal registers
    logic [2:0]  state, next_state;
    logic        internal_next_player;
    logic [7:0]  turn_count;
    logic [1:0]  pass_count;                 // Count consecutive passes
    logic [1:0]  recent_moves [0:7];         // Track recent moves (0=normal, 1=pass)
    logic [2:0]  recent_move_index;
    logic        excessive_passing;
    logic        game_end_detected;
    
    // Internal variables (FIXED: declared at module level)
    logic [3:0] pass_count_internal;
    logic [3:0] recent_pass_count;
    
    // State encoding
    localparam IDLE = 3'b000;
    localparam CHECK_CONDITIONS = 3'b001;
    localparam SWITCH_PLAYER = 3'b010;
    localparam UPDATE_HISTORY = 3'b011;
    localparam COMPLETE = 3'b100;
    
    // Maximum turns for 7x7 board (safety limit)
    localparam MAX_TURNS = 8'd98; // 2 * 49 positions
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            internal_next_player <= 1'b0; // Start with black
            turn_count <= '0;
            pass_count <= '0;
            recent_move_index <= '0;
            game_end_detected <= 1'b0;
            excessive_passing <= 1'b0;
            // Initialize recent moves array
            for (int i = 0; i < 8; i++) begin
                recent_moves[i] <= 2'b00;
            end
        end else begin
            state <= next_state;
            
            case (state)
                CHECK_CONDITIONS: begin
                    // Check for game ending conditions
                    game_end_detected <= (empty_count == 0) || 
                                        (pass_count >= 2) || 
                                        (turn_count >= MAX_TURNS) ||
                                        excessive_passing;
                end
                
                SWITCH_PLAYER: begin
                    if (!game_end_detected && move_applied) begin
                        internal_next_player <= ~current_player;
                        turn_count <= turn_count + 1;
                        
                        // Update pass tracking
                        if (pass_move) begin
                            pass_count <= pass_count + 1;
                        end else begin
                            pass_count <= '0; // Reset on normal move
                        end
                    end
                end
                
                UPDATE_HISTORY: begin
                    // Update recent moves history for pattern detection
                    recent_moves[recent_move_index] <= {1'b0, pass_move};
                    recent_move_index <= (recent_move_index + 1) % 8;
                    
                    // Check for excessive passing (more than 4 passes in last 8 moves)
                    pass_count_internal = 0;
                    for (int k = 0; k < 8; k++) begin
                        if (recent_moves[k][0]) pass_count_internal++;
                    end
                    excessive_passing <= (pass_count_internal > 4);
                end
                
                IDLE: begin
                    // Reset counters when idle
                    if (!enable) begin
                        pass_count <= '0;
                        recent_move_index <= '0;
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
                if (enable && move_applied)
                    next_state = CHECK_CONDITIONS;
            end
            
            CHECK_CONDITIONS:
                next_state = SWITCH_PLAYER;
                
            SWITCH_PLAYER:
                next_state = UPDATE_HISTORY;
                
            UPDATE_HISTORY:
                next_state = COMPLETE;
                
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // Game state analysis
    logic territory_exhausted;
    logic move_cycles_detected;
    
    always_comb begin
        // Territory exhausted when very few empty positions remain
        territory_exhausted = (empty_count <= 2);
        
        // Simple cycle detection (could be enhanced)
        move_cycles_detected = (turn_count > 20) && excessive_passing;
    end
    
    // Advanced game ending conditions for 7x7
    logic advanced_game_end;
    always_comb begin
        advanced_game_end = territory_exhausted || 
                           move_cycles_detected ||
                           (turn_count >= MAX_TURNS);
    end
    
    // Turn validation logic
    logic turn_sequence_valid;
    always_comb begin
        turn_sequence_valid = (turn_count < MAX_TURNS) && 
                             !excessive_passing &&
                             !game_over;
    end
    
    // Output assignments
    assign next_player = internal_next_player;
    assign turn_complete = (state == COMPLETE);
    assign switch_valid = (state == COMPLETE) && turn_sequence_valid;
    assign game_state_valid = turn_sequence_valid && !game_end_detected;
    assign turn_counter = turn_count;
    assign consecutive_passes = (pass_count >= 2);
    assign board_full = (empty_count == 0);
    assign game_end_condition = game_end_detected || advanced_game_end || game_over;

endmodule
