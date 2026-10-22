// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Move Generator for 5x5 Go Board
// Generates valid moves from empty positions for MCTS expansion
// Supports move ordering and filtering based on game rules

module move_generator_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [24:0] empty_positions,     // Bit mask from empty position detector
    input  logic [4:0]  empty_count,        // Number of empty positions
    input  logic [49:0] board_state,        // Current board state (50 bits, 2 bits per position)
    input  logic        current_player,     // 0=black, 1=white
    input  logic [1:0]  move_selection_mode, // 00=sequential, 01=random, 10=priority, 11=all
    output logic [4:0]  generated_move,     // Selected move position (0-24)
    output logic        move_valid,
    output logic        move_ready,
    output logic        generation_complete,
    
    // Multiple moves output for batch processing
    output logic [4:0]  moves_list [0:24],  // All valid moves
    output logic [4:0]  moves_count,        // Number of valid moves generated
    output logic        all_moves_ready
);

    // Internal registers
    logic [3:0]  state, next_state;
    logic [4:0]  current_position;
    logic [4:0]  move_counter;
    logic [4:0]  selected_move;
    logic [4:0]  moves_buffer [0:24];
    logic [4:0]  valid_moves_count;
    
    // LFSR for random move selection
    logic [7:0]  lfsr_state;
    logic [4:0]  random_index;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam SCAN_EMPTY = 4'b0001;
    localparam VALIDATE_MOVE = 4'b0010;
    localparam ADD_TO_LIST = 4'b0011;
    localparam SELECT_MOVE = 4'b0100;
    localparam COMPLETE = 4'b0101;
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            current_position <= '0;
            move_counter <= '0;
        end else begin
            state <= next_state;
            case (state)
                SCAN_EMPTY: begin
                    if (current_position < 24) begin
                        current_position <= current_position + 1;
                    end
                end
                ADD_TO_LIST: begin
                    move_counter <= move_counter + 1;
                end
                IDLE: begin
                    current_position <= '0;
                    move_counter <= '0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        case (state)
            IDLE: if (enable) next_state = SCAN_EMPTY;
            SCAN_EMPTY: begin
                if (current_position == 24) begin
                    next_state = SELECT_MOVE;
                end else if (empty_positions[current_position]) begin
                    next_state = VALIDATE_MOVE;
                end
            end
            VALIDATE_MOVE: next_state = ADD_TO_LIST;
            ADD_TO_LIST: next_state = SCAN_EMPTY;
            SELECT_MOVE: next_state = COMPLETE;
            COMPLETE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end
    
    // Move validation logic
    logic position_is_valid;
    logic [1:0] pos_state;
    
    always_comb begin
        position_is_valid = 1'b1; // Default valid
        
        // Check if position is truly empty
        if (current_position < 25) begin
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
    
    // Move list management
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < 25; i++) begin
                moves_buffer[i] <= '0;
            end
            valid_moves_count <= '0;
        end else if (state == ADD_TO_LIST && position_is_valid) begin
            moves_buffer[move_counter] <= current_position;
            valid_moves_count <= move_counter + 1;
        end else if (state == IDLE) begin
            valid_moves_count <= '0;
        end
    end
    
    // LFSR for random number generation
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            lfsr_state <= 8'b10110101; // Initial seed
        end else begin
            // 8-bit LFSR with taps at positions 8,6,5,4
            lfsr_state <= {lfsr_state[6:0], lfsr_state[7] ^ lfsr_state[5] ^ lfsr_state[4] ^ lfsr_state[3]};
        end
    end
    
    assign random_index = lfsr_state[4:0] % (valid_moves_count ? valid_moves_count : 5'd1);
    
    // Move selection based on mode
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            selected_move <= '0;
        end else if (state == SELECT_MOVE) begin
            case (move_selection_mode)
                2'b00: begin // Sequential - first available move
                    selected_move <= valid_moves_count > 0 ? moves_buffer[0] : 5'b11111;
                end
                2'b01: begin // Random selection
                    selected_move <= valid_moves_count > 0 ? moves_buffer[random_index] : 5'b11111;
                end
                2'b10: begin // Priority-based (corner/edge preference for Go)
                    selected_move <= get_priority_move();
                end
                2'b11: begin // All moves mode - return first for now
                    selected_move <= valid_moves_count > 0 ? moves_buffer[0] : 5'b11111;
                end
                default: selected_move <= 5'b11111;
            endcase
        end
    end
    
    // Priority move selection function
    function logic [4:0] get_priority_move();
        logic [4:0] best_move;
        logic [2:0] best_priority;
        logic [2:0] current_priority;
        
        best_move = 5'b11111;
        best_priority = 3'b000;
        
        for (int j = 0; j < valid_moves_count && j < 25; j++) begin
            current_priority = calculate_move_priority(moves_buffer[j]);
            if (current_priority > best_priority) begin
                best_priority = current_priority;
                best_move = moves_buffer[j];
            end
        end
        
        return best_move;
    endfunction
    
    // Calculate move priority (corner > edge > center for 5x5)
    function logic [2:0] calculate_move_priority(input logic [4:0] pos);
        int row, col;
        row = pos / 5;
        col = pos % 5;
        
        // Corner positions get highest priority
        if ((row == 0 || row == 4) && (col == 0 || col == 4)) begin
            return 3'b111;
        end
        // Edge positions get medium priority  
        else if (row == 0 || row == 4 || col == 0 || col == 4) begin
            return 3'b100;
        end
        // Center positions get lowest priority
        else begin
            return 3'b001;
        end
    endfunction
    
    // Output assignments
    assign generated_move = selected_move;
    assign move_valid = (selected_move != 5'b11111) && (state == COMPLETE);
    assign move_ready = (state == COMPLETE);
    assign generation_complete = (state == COMPLETE);
    
    // Batch output assignments
    always_comb begin
        for (int k = 0; k < 25; k++) begin
            moves_list[k] = moves_buffer[k];
        end
    end
    
    assign moves_count = valid_moves_count;
    assign all_moves_ready = (state == COMPLETE);
    
    // Additional status outputs
    logic has_valid_moves;
    assign has_valid_moves = (valid_moves_count > 0);
    
    // Debug information
    logic [24:0] processed_positions;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            processed_positions <= '0;
        end else if (state == SCAN_EMPTY) begin
            processed_positions[current_position] <= 1'b1;
        end else if (state == IDLE) begin
            processed_positions <= '0;
        end
    end
    
endmodule
