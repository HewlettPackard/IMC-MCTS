// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Win Decision Logic for 7x7 Go Board
// Analyzes rollout results to determine game winner using Go scoring rules
// Implements territory counting, capture analysis, and komi scoring

module win_decision_logic_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [97:0] board_state,             // Final board state (98 bits, 2 bits per position)
    input  logic [7:0]  komi_value,              // Komi compensation value (typically 6.5 × 2 = 13)
    input  logic        evaluate_enable,
    input  logic        rollout_complete,
    input  logic [5:0]  captured_black,          // Black stones captured during game
    input  logic [5:0]  captured_white,          // White stones captured during game
    output logic [1:0]  winner,                  // 00=draw, 01=black wins, 10=white wins, 11=invalid
    output logic [7:0]  black_score,             // Final score for black player
    output logic [7:0]  white_score,             // Final score for white player
    output logic [7:0]  score_difference,        // Absolute score difference
    output logic        evaluation_valid,
    output logic [48:0] territory_map,           // Territory ownership map for debugging
    output logic        evaluation_complete
);

    // Internal registers
    logic [3:0]  state, next_state;
    logic [5:0]  position_counter;
    logic [7:0]  black_territory;
    logic [7:0]  white_territory;
    logic [7:0]  black_stones;
    logic [7:0]  white_stones;
    logic [48:0] territory_ownership;            // 0=black territory, 1=white territory
    logic [48:0] neutral_territory;              // Positions that are neutral/contested
    logic [7:0]  final_black_score;
    logic [7:0]  final_white_score;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam COUNT_STONES = 4'b0001;
    localparam ANALYZE_TERRITORY = 4'b0010;
    localparam FLOOD_FILL_BLACK = 4'b0011;
    localparam FLOOD_FILL_WHITE = 4'b0100;
    localparam CALCULATE_SCORES = 4'b0101;
    localparam APPLY_KOMI = 4'b0110;
    localparam DETERMINE_WINNER = 4'b0111;
    localparam COMPLETE = 4'b1000;
    
    // Board position decoding for 7x7 (49 positions)
    logic [1:0] position_states [0:48];
    
    genvar i;
    generate
        for (i = 0; i < 49; i++) begin : pos_decode
            assign position_states[i] = board_state[2*i+1:2*i];
        end
    endgenerate
    
    // Territory analysis masks
    logic [48:0] black_stone_mask;
    logic [48:0] white_stone_mask;
    logic [48:0] empty_mask;
    
    always_comb begin
        black_stone_mask = '0;
        white_stone_mask = '0;
        empty_mask = '0;
        
        for (int j = 0; j < 49; j++) begin
            case (position_states[j])
                2'b00: empty_mask[j] = 1'b1;
                2'b01: black_stone_mask[j] = 1'b1;
                2'b10: white_stone_mask[j] = 1'b1;
                default: ; // Invalid state
            endcase
        end
    end
    
    // Neighbor calculation for 7x7 grid
    function logic [48:0] get_neighbors(input logic [5:0] pos);
        logic [48:0] neighbors;
        logic [2:0] row, col;
        neighbors = '0;
        
        if (pos < 49) begin
            row = pos / 7;
            col = pos % 7;
            
            // North neighbor
            if (row > 0)
                neighbors[pos - 7] = 1'b1;
            // South neighbor
            if (row < 6)
                neighbors[pos + 7] = 1'b1;
            // West neighbor
            if (col > 0)
                neighbors[pos - 1] = 1'b1;
            // East neighbor
            if (col < 6)
                neighbors[pos + 1] = 1'b1;
        end
        
        return neighbors;
    endfunction
    
    // Territory ownership determination using simplified flood-fill
    function logic determine_territory_owner(input logic [5:0] empty_pos);
        logic [48:0] neighbors;
        logic has_black_neighbor, has_white_neighbor;
        
        has_black_neighbor = 1'b0;
        has_white_neighbor = 1'b0;
        
        if (empty_pos < 49) begin
            neighbors = get_neighbors(empty_pos);
            
            // Check immediate neighbors for influence
            for (int k = 0; k < 49; k++) begin
                if (neighbors[k]) begin
                    if (black_stone_mask[k])
                        has_black_neighbor = 1'b1;
                    if (white_stone_mask[k])
                        has_white_neighbor = 1'b1;
                end
            end
            
            // Determine ownership based on surrounding stones
            if (has_black_neighbor && !has_white_neighbor)
                return 1'b0; // Black territory
            else if (has_white_neighbor && !has_black_neighbor)
                return 1'b1; // White territory
            else
                return 1'b0; // Neutral/contested (default to black for tie-breaking)
        end
        
        return 1'b0;
    endfunction
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            position_counter <= '0;
            black_territory <= '0;
            white_territory <= '0;
            black_stones <= '0;
            white_stones <= '0;
            territory_ownership <= '0;
            neutral_territory <= '0;
            final_black_score <= '0;
            final_white_score <= '0;
        end else begin
            state <= next_state;
            
            case (state)
                COUNT_STONES: begin
                    black_stones <= '0;
                    white_stones <= '0;
                    
                    // Count stones on board
                    for (int m = 0; m < 49; m++) begin
                        if (black_stone_mask[m])
                            black_stones <= black_stones + 1;
                        if (white_stone_mask[m])
                            white_stones <= white_stones + 1;
                    end
                end
                
                ANALYZE_TERRITORY: begin
                    black_territory <= '0;
                    white_territory <= '0;
                    territory_ownership <= '0;
                    
                    // Analyze territory ownership for empty positions
                    for (int n = 0; n < 49; n++) begin
                        if (empty_mask[n]) begin
                            if (determine_territory_owner(n[5:0])) begin
                                white_territory <= white_territory + 1;
                                territory_ownership[n] <= 1'b1;
                            end else begin
                                black_territory <= black_territory + 1;
                                territory_ownership[n] <= 1'b0;
                            end
                        end
                    end
                end
                
                CALCULATE_SCORES: begin
                    // Calculate base scores (stones + territory)
                    final_black_score <= black_stones + black_territory;
                    final_white_score <= white_stones + white_territory;
                end
                
                APPLY_KOMI: begin
                    // Apply komi compensation to white
                    final_white_score <= final_white_score + komi_value;
                    
                    // Subtract captured stones
                    if (final_black_score > captured_black)
                        final_black_score <= final_black_score - captured_black;
                    else
                        final_black_score <= '0;
                        
                    if (final_white_score > captured_white)
                        final_white_score <= final_white_score - captured_white;
                    else
                        final_white_score <= '0;
                end
                
                DETERMINE_WINNER: begin
                    // Determine winner and score difference
                    if (final_black_score > final_white_score) begin
                        winner <= 2'b01; // Black wins
                        score_difference <= final_black_score - final_white_score;
                    end else if (final_white_score > final_black_score) begin
                        winner <= 2'b10; // White wins
                        score_difference <= final_white_score - final_black_score;
                    end else begin
                        winner <= 2'b00; // Draw
                        score_difference <= '0;
                    end
                end
                
                IDLE: begin
                    position_counter <= '0;
                    black_territory <= '0;
                    white_territory <= '0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        
        case (state)
            IDLE: begin
                if (enable && evaluate_enable && rollout_complete)
                    next_state = COUNT_STONES;
            end
            
            COUNT_STONES:
                next_state = ANALYZE_TERRITORY;
                
            ANALYZE_TERRITORY:
                next_state = CALCULATE_SCORES;
                
            CALCULATE_SCORES:
                next_state = APPLY_KOMI;
                
            APPLY_KOMI:
                next_state = DETERMINE_WINNER;
                
            DETERMINE_WINNER:
                next_state = COMPLETE;
                
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // Output assignments
    assign black_score = final_black_score;
    assign white_score = final_white_score;
    assign evaluation_valid = (state == COMPLETE);
    assign evaluation_complete = (state == COMPLETE);
    assign territory_map = territory_ownership;

endmodule
