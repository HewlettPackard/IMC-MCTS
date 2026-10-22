// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Move Generator for 7x7 Go Board
// Generates valid moves from empty positions for MCTS expansion
// Supports move ordering and filtering based on game rules for 49 positions

module move_generator_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [48:0] empty_positions,     // Bit mask from empty position detector
    input  logic [5:0]  empty_count,        // Number of empty positions
    input  logic [97:0] board_state,        // Current board state (98 bits, 2 bits per position)
    input  logic        current_player,     // 0=black, 1=white
    input  logic [1:0]  move_selection_mode, // 00=sequential, 01=random, 10=priority, 11=all
    output logic [5:0]  generated_move,     // Selected move position (0-48)
    output logic        move_valid,
    output logic        move_ready,
    output logic        generation_complete,
    
    // Multiple moves output for batch processing
    output logic [5:0]  moves_list [0:48],  // All valid moves (up to 49)
    output logic [5:0]  moves_count,        // Number of valid moves generated
    output logic        all_moves_ready
);

    // Internal registers
    logic [3:0]  state, next_state;
    logic [5:0]  current_position;
    logic [5:0]  move_counter;
    logic [5:0]  selected_move;
    logic [5:0]  moves_buffer [0:48];       // Buffer for 49 moves (FIXED: proper bounds)
    logic [5:0]  valid_moves_count;
    
    // LFSR for random move selection
    logic [7:0]  lfsr_state;
    logic [5:0]  random_index;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam SCAN_EMPTY = 4'b0001;
    localparam VALIDATE_MOVE = 4'b0010;
    localparam ADD_TO_LIST = 4'b0011;
    localparam SELECT_MOVE = 4'b0100;
    localparam COMPLETE = 4'b0101;
    
    // Position validation logic
    logic position_is_valid;
    logic [1:0] pos_state;
    
    always_comb begin
        position_is_valid = 1'b1; // Default valid
        
        // Check if position is truly empty
        if (current_position < 49) begin
            pos_state = board_state[2*current_position+1:2*current_position];
            position_is_valid = (pos_state == 2'b00);
        end else begin
            position_is_valid = 1'b0;
        end
        
        // Additional Go rules validation could be added here:
        // - Ko rule checking
        // - Suicide move detection
        // - Superko checking
    end
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            current_position <= '0;
            move_counter <= '0;
            selected_move <= 6'd49; // Invalid position marker
            valid_moves_count <= '0;
            lfsr_state <= 8'h1;
            // Initialize moves buffer
            for (int i = 0; i < 49; i++) begin
                moves_buffer[i] <= 6'd49;
            end
        end else begin
            state <= next_state;
            
            case (state)
                SCAN_EMPTY: begin
                    if (current_position < 49) begin
                        if (empty_positions[current_position]) begin
                            current_position <= current_position + 1;
                        end else begin
                            current_position <= current_position + 1;
                        end
                    end
                end
                
                VALIDATE_MOVE: begin
                    // Position validation done in combinatorial logic
                end
                
                ADD_TO_LIST: begin
                    if (position_is_valid && valid_moves_count < 49) begin
                        moves_buffer[valid_moves_count] <= current_position;
                        valid_moves_count <= valid_moves_count + 1;
                    end
                end
                
                SELECT_MOVE: begin
                    case (move_selection_mode)
                        2'b00: // Sequential - first valid move
                            selected_move <= (valid_moves_count > 0) ? moves_buffer[0] : 6'd49;
                            
                        2'b01: // Random selection
                            if (valid_moves_count > 0) begin
                                random_index <= lfsr_state[5:0] % valid_moves_count;
                                selected_move <= moves_buffer[random_index];
                                // Update LFSR
                                lfsr_state <= {lfsr_state[6:0], lfsr_state[7] ^ lfsr_state[5] ^ 
                                              lfsr_state[4] ^ lfsr_state[3]};
                            end else begin
                                selected_move <= 6'd49;
                            end
                            
                        2'b10: // Priority-based selection
                            selected_move <= select_priority_move();
                            
                        2'b11: // All moves mode
                            selected_move <= (valid_moves_count > 0) ? moves_buffer[0] : 6'd49;
                            
                        default:
                            selected_move <= 6'd49;
                    endcase
                end
                
                IDLE: begin
                    current_position <= '0;
                    move_counter <= '0;
                    valid_moves_count <= '0;
                    lfsr_state <= 8'h1;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        
        case (state)
            IDLE: begin
                if (enable && empty_count > 0)
                    next_state = SCAN_EMPTY;
            end
            
            SCAN_EMPTY: begin
                if (current_position < 49) begin
                    if (empty_positions[current_position])
                        next_state = VALIDATE_MOVE;
                    else if (current_position >= 48)
                        next_state = SELECT_MOVE;
                end else begin
                    next_state = SELECT_MOVE;
                end
            end
            
            VALIDATE_MOVE:
                next_state = ADD_TO_LIST;
                
            ADD_TO_LIST: begin
                if (current_position >= 48)
                    next_state = SELECT_MOVE;
                else
                    next_state = SCAN_EMPTY;
            end
            
            SELECT_MOVE:
                next_state = COMPLETE;
                
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // Priority-based move selection function
    function logic [5:0] select_priority_move();
        logic [5:0] best_move;
        logic [2:0] best_priority;
        logic [2:0] current_priority;
        
        best_move = 6'd49;
        best_priority = 3'b000;
        
        for (int j = 0; j < 49 && j < valid_moves_count; j++) begin // FIXED: bounds checking
            current_priority = calculate_move_priority(moves_buffer[j]);
            if (current_priority > best_priority) begin
                best_priority = current_priority;
                best_move = moves_buffer[j];
            end
        end
        
        return best_move;
    endfunction
    
    // Calculate move priority (corner > edge > center for 7x7)
    function logic [2:0] calculate_move_priority(input logic [5:0] pos);
        logic [2:0] row, col;
        logic [2:0] priority;
        
        priority = 3'b001; // Default center priority
        
        if (pos < 49) begin
            row = pos / 7;
            col = pos % 7;
            
            // Corner positions (highest priority)
            if ((row == 0 || row == 6) && (col == 0 || col == 6)) begin
                priority = 3'b111;
            end
            // Edge positions (medium priority)  
            else if (row == 0 || row == 6 || col == 0 || col == 6) begin
                priority = 3'b100;
            end
            // Center positions (lower priority)
            else begin
                priority = 3'b010;
            end
        end
        
        return priority;
    endfunction
    
    // Move list management
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < 49; i++) begin
                moves_buffer[i] <= 6'd49;
            end
            valid_moves_count <= '0;
        end else begin
            // Handled in main state machine
        end
    end
    
    // Output assignments
    assign generated_move = selected_move;
    assign move_valid = (selected_move < 49) && (state == COMPLETE);
    assign move_ready = (state == COMPLETE);
    assign generation_complete = (state == COMPLETE);
    assign moves_count = valid_moves_count;
    assign all_moves_ready = (state == COMPLETE);
    
    // Copy moves buffer to output list
    genvar k;
    generate
        for (k = 0; k < 49; k++) begin : moves_assign
            assign moves_list[k] = moves_buffer[k];
        end
    endgenerate

endmodule
