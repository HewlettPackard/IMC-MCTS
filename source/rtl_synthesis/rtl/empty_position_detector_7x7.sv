// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Empty Position Detector for 7x7 Go Board
// Scans board state to find all empty positions for move generation
// Optimized for 49-position detection with parallel processing

module empty_position_detector_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [97:0] board_state,         // 7x7 board state (98 bits, 2 bits per position)
    input  logic [7:0]  random_seed,         // Seed for random empty position selection
    output logic [48:0] empty_positions,     // Bit mask of empty positions
    output logic [5:0]  empty_count,         // Number of empty positions (0-49)
    output logic [5:0]  first_empty_position, // Index of first empty position
    output logic [5:0]  selected_empty_position, // Randomly selected empty position
    output logic        scan_complete,
    output logic        positions_valid,
    output logic        has_empty_positions
);

    // Internal registers
    logic [2:0]  state, next_state;
    logic [48:0] empty_mask;
    logic [5:0]  count_reg;
    logic [5:0]  position_counter;
    logic [5:0]  first_empty;
    logic [5:0]  selected_position;
    
    // State encoding
    localparam IDLE = 3'b000;
    localparam SCAN_POSITIONS = 3'b001;
    localparam COUNT_EMPTY = 3'b010;
    localparam SELECT_RANDOM = 3'b011;
    localparam COMPLETE = 3'b100;
    
    // Board position decoding for 7x7 (49 positions)
    logic [1:0] position_states [0:48];
    
    // Generate array assignments for easier access (FIXED: correct bit width)
    genvar i;
    generate
        for (i = 0; i < 49; i++) begin : pos_decode
            assign position_states[i] = board_state[2*i+1:2*i];
        end
    endgenerate
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            position_counter <= '0;
            empty_mask <= '0;
            count_reg <= '0;
            first_empty <= 6'd49; // Invalid position
            selected_position <= 6'd49;
        end else begin
            state <= next_state;
            
            case (state)
                SCAN_POSITIONS: begin
                    if (position_counter < 49) begin
                        // Check if current position is empty
                        if (position_states[position_counter] == 2'b00) begin
                            empty_mask[position_counter] <= 1'b1;
                            if (first_empty == 6'd49) // First empty position found
                                first_empty <= position_counter;
                        end else begin
                            empty_mask[position_counter] <= 1'b0;
                        end
                        position_counter <= position_counter + 1;
                    end
                end
                
                COUNT_EMPTY: begin
                    count_reg <= '0;
                    // Count all empty positions
                    for (int j = 0; j < 49; j++) begin
                        if (empty_mask[j])
                            count_reg <= count_reg + 1;
                    end
                end
                
                SELECT_RANDOM: begin
                    // Select random empty position if multiple exist
                    if (count_reg > 0) begin
                        selected_position <= select_random_empty();
                    end else begin
                        selected_position <= 6'd49; // No empty positions
                    end
                end
                
                IDLE: begin
                    position_counter <= '0;
                    empty_mask <= '0;
                    count_reg <= '0;
                    first_empty <= 6'd49;
                    selected_position <= 6'd49;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        
        case (state)
            IDLE: begin
                if (enable)
                    next_state = SCAN_POSITIONS;
            end
            
            SCAN_POSITIONS: begin
                if (position_counter >= 49)
                    next_state = COUNT_EMPTY;
            end
            
            COUNT_EMPTY:
                next_state = SELECT_RANDOM;
                
            SELECT_RANDOM:
                next_state = COMPLETE;
                
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // Function to select random empty position
    logic [5:0] target_index;
    logic [5:0] current_index;
    
    function logic [5:0] select_random_empty();
        logic [5:0] target_idx;
        logic [5:0] curr_idx;
        logic [5:0] result;
        
        result = first_empty; // Default to first empty
        
        if (count_reg > 1) begin
            target_idx = random_seed % count_reg;
            curr_idx = 0;
            
            for (int n = 0; n < 49; n++) begin
                if (empty_mask[n]) begin
                    if (curr_idx == target_idx) begin
                        result = n[5:0];
                        break;
                    end
                    curr_idx++;
                end
            end
        end
        
        return result;
    endfunction
    
    // Parallel empty position detection (combinatorial for faster operation)
    logic [48:0] parallel_empty_mask;
    logic [5:0]  parallel_count;
    logic [5:0]  parallel_first_empty;
    
    always_comb begin
        parallel_empty_mask = '0;
        parallel_count = '0;
        parallel_first_empty = 6'd49;
        
        // Generate empty mask and count in parallel
        for (int k = 0; k < 49; k++) begin
            if (position_states[k] == 2'b00) begin
                parallel_empty_mask[k] = 1'b1;
                parallel_count++;
                if (parallel_first_empty == 6'd49)
                    parallel_first_empty = k[5:0];
            end
        end
    end
    
    // Fast mode detection (bypass state machine for simple cases)
    logic fast_mode_enable;
    assign fast_mode_enable = enable && (state == IDLE);
    
    // Output assignments
    assign empty_positions = fast_mode_enable ? parallel_empty_mask : empty_mask;
    assign empty_count = fast_mode_enable ? parallel_count : count_reg;
    assign first_empty_position = fast_mode_enable ? parallel_first_empty : first_empty;
    assign selected_empty_position = selected_position;
    assign scan_complete = (state == COMPLETE) || fast_mode_enable;
    assign positions_valid = (state == COMPLETE) || fast_mode_enable;
    assign has_empty_positions = (empty_count > 0);

endmodule
