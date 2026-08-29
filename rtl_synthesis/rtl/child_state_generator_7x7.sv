// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Child State Generator for 7x7 Go Board
// Generates new board states by applying moves during MCTS expansion
// Handles 7x7 board state transitions with proper stone placement and capture logic

module child_state_generator_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [97:0] parent_board_state,  // Current 7x7 board state (98 bits, 2 bits per position)
    input  logic        current_player,      // 0=black, 1=white
    input  logic [5:0]  move_position,       // Position to place stone (0-48)
    input  logic        move_valid,          // Move validation signal
    output logic [97:0] child_board_state,   // New board state after move (98 bits, 2 bits per position)
    output logic        state_valid,
    output logic        generation_complete,
    output logic        capture_occurred,
    
    // Additional game state information
    output logic [5:0]  captured_stones,     // Number of stones captured
    output logic [48:0] capture_mask,        // Bit mask of captured positions
    output logic        illegal_move         // Move violates Go rules
);

    // Internal registers
    logic [2:0]  state, next_state;
    logic [97:0] working_board_state;
    logic [48:0] position_empty_mask;        // Mask of empty positions
    logic [48:0] black_stone_mask;           // Mask of black stone positions
    logic [48:0] white_stone_mask;           // Mask of white stone positions
    logic [5:0]  current_position;
    logic [5:0]  capture_count;
    logic [48:0] temp_capture_mask;
    
    // State encoding
    localparam IDLE = 3'b000;
    localparam VALIDATE_MOVE = 3'b001;
    localparam PLACE_STONE = 3'b010;
    localparam CHECK_CAPTURES = 3'b011;
    localparam APPLY_CAPTURES = 3'b100;
    localparam COMPLETE = 3'b101;
    
    // Board position decoding for 7x7 (49 positions)
    logic [1:0] position_states [0:48];
    genvar i;
    generate
        for (i = 0; i < 49; i++) begin : pos_decode
            assign position_states[i] = working_board_state[2*i+1:2*i];
        end
    endgenerate
    
    // Generate position masks
    always_comb begin
        position_empty_mask = '0;
        black_stone_mask = '0;
        white_stone_mask = '0;
        
        for (int j = 0; j < 49; j++) begin
            position_empty_mask[j] = (position_states[j] == 2'b00);
            black_stone_mask[j] = (position_states[j] == 2'b01);
            white_stone_mask[j] = (position_states[j] == 2'b10);
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
    
    // Check for captures using flood-fill approach
    function logic [48:0] find_captured_group(input logic [5:0] start_pos, input logic [48:0] same_color_mask);
        logic [48:0] group_mask;
        logic [48:0] visited_mask;
        logic [48:0] to_visit_mask;
        logic [48:0] neighbors;
        logic has_liberty;
        int visit_pos;
        
        group_mask = '0;
        visited_mask = '0;
        to_visit_mask = '0;
        has_liberty = 1'b0;
        
        if (start_pos < 49 && same_color_mask[start_pos]) begin
            to_visit_mask[start_pos] = 1'b1;
            
            // Simplified flood-fill (would need proper implementation for synthesis)
            for (int iter = 0; iter < 49; iter++) begin
                if (to_visit_mask != '0) begin
                    // Find first position to visit
                    for (int k = 0; k < 49; k++) begin
                        if (to_visit_mask[k] && !visited_mask[k]) begin
                            visit_pos = k;
                            break;
                        end
                    end
                    
                    visited_mask[visit_pos] = 1'b1;
                    group_mask[visit_pos] = 1'b1;
                    to_visit_mask[visit_pos] = 1'b0;
                    
                    neighbors = get_neighbors(visit_pos[5:0]);
                    
                    // Check for liberties (empty neighbors)
                    if ((neighbors & position_empty_mask) != '0)
                        has_liberty = 1'b1;
                    
                    // Add same-color neighbors to visit list
                    to_visit_mask |= (neighbors & same_color_mask & ~visited_mask);
                end
            end
        end
        
        return has_liberty ? 49'h0 : group_mask;
    endfunction
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            working_board_state <= '0;
            current_position <= '0;
            capture_count <= '0;
            temp_capture_mask <= '0;
        end else begin
            state <= next_state;
            
            case (state)
                VALIDATE_MOVE: begin
                    working_board_state <= parent_board_state;
                    current_position <= move_position;
                    capture_count <= '0;
                    temp_capture_mask <= '0;
                end
                
                PLACE_STONE: begin
                    if (move_position < 49 && position_empty_mask[move_position]) begin
                        // Place stone at specified position
                        working_board_state[2*move_position+1:2*move_position] <= 
                            current_player ? 2'b10 : 2'b01;
                    end
                end
                
                CHECK_CAPTURES: begin
                    logic [48:0] neighbors;
                    logic [48:0] opponent_mask;
                    logic [48:0] captured_group;
                    
                    neighbors = get_neighbors(move_position);
                    opponent_mask = current_player ? black_stone_mask : white_stone_mask;
                    
                    // Check each opponent neighbor for capture
                    for (int n = 0; n < 49; n++) begin
                        if (neighbors[n] && opponent_mask[n]) begin
                            captured_group = find_captured_group(n[5:0], opponent_mask);
                            temp_capture_mask |= captured_group;
                        end
                    end
                end
                
                APPLY_CAPTURES: begin
                    capture_count <= '0;
                    for (int c = 0; c < 49; c++) begin
                        if (temp_capture_mask[c]) begin
                            working_board_state[2*c+1:2*c] <= 2'b00; // Remove captured stone
                            capture_count <= capture_count + 1;
                        end
                    end
                end
                
                IDLE: begin
                    working_board_state <= '0;
                    temp_capture_mask <= '0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        
        case (state)
            IDLE: begin
                if (enable && move_valid)
                    next_state = VALIDATE_MOVE;
            end
            
            VALIDATE_MOVE: begin
                if (move_position < 49 && position_empty_mask[move_position])
                    next_state = PLACE_STONE;
                else
                    next_state = COMPLETE; // Illegal move
            end
            
            PLACE_STONE:
                next_state = CHECK_CAPTURES;
                
            CHECK_CAPTURES:
                next_state = APPLY_CAPTURES;
                
            APPLY_CAPTURES:
                next_state = COMPLETE;
                
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // Move validation
    logic move_position_valid;
    always_comb begin
        move_position_valid = (move_position < 49) && 
                             (position_states[move_position] == 2'b00) && 
                             move_valid;
    end
    
    // Output assignments
    assign child_board_state = working_board_state;
    assign state_valid = (state == COMPLETE) && move_position_valid;
    assign generation_complete = (state == COMPLETE);
    assign capture_occurred = (capture_count > 0);
    assign captured_stones = capture_count;
    assign capture_mask = temp_capture_mask;
    assign illegal_move = (state == COMPLETE) && !move_position_valid;

endmodule
