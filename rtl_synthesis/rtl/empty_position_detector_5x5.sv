// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Empty Position Detector for 5x5 Go Board
// Scans board state to find all empty positions for move generation
// Outputs bit mask and count of available moves

module empty_position_detector_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [49:0] board_state,         // 5x5 board state (50 bits total, 2 bits per position)
    output logic [24:0] empty_positions,     // Bit mask of empty positions
    output logic [4:0]  empty_count,        // Number of empty positions (0-25)
    output logic        scan_complete,
    output logic        positions_valid
);

    // Internal registers
    logic [2:0]  state, next_state;
    logic [24:0] empty_mask;
    logic [4:0]  count_reg;
    logic [4:0]  position_counter;
    
    // State encoding
    localparam IDLE = 3'b000;
    localparam SCAN_POSITIONS = 3'b001;
    localparam COUNT_EMPTY = 3'b010;
    localparam COMPLETE = 3'b011;
    
    // Board position decoding
    logic [1:0] position_states [0:24];
    
    // Generate array assignments for easier access
    genvar i;
    generate
        for (i = 0; i < 25; i++) begin : pos_decode
            assign position_states[i] = board_state[2*i+1:2*i];
        end
    endgenerate
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            position_counter <= '0;
        end else begin
            state <= next_state;
            if (state == SCAN_POSITIONS && position_counter < 24) begin
                position_counter <= position_counter + 1;
            end else if (state == IDLE) begin
                position_counter <= '0;
            end
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        case (state)
            IDLE: if (enable) next_state = SCAN_POSITIONS;
            SCAN_POSITIONS: if (position_counter == 24) next_state = COUNT_EMPTY;
            COUNT_EMPTY: next_state = COMPLETE;
            COMPLETE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end
    
    // Empty position detection logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            empty_mask <= '0;
        end else if (state == SCAN_POSITIONS) begin
            // Check each position for emptiness (00 = empty)
            for (int j = 0; j < 25; j++) begin
                empty_mask[j] <= (position_states[j] == 2'b00);
            end
        end
    end
    
    // Parallel counting using population count
    logic [4:0] popcount_result;
    
    always_comb begin
        popcount_result = 5'b0;
        for (int k = 0; k < 25; k++) begin
            popcount_result = popcount_result + empty_mask[k];
        end
    end
    
    // Register the count
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            count_reg <= '0;
        end else if (state == COUNT_EMPTY) begin
            count_reg <= popcount_result;
        end
    end
    
    // Alternative serial counting approach for area optimization
    logic [4:0] serial_count;
    logic [4:0] count_index;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            serial_count <= '0;
            count_index <= '0;
        end else if (state == SCAN_POSITIONS) begin
            if (count_index < 25) begin
                if (position_states[count_index] == 2'b00) begin
                    serial_count <= serial_count + 1;
                end
                count_index <= count_index + 1;
            end
        end else if (state == IDLE) begin
            serial_count <= '0;
            count_index <= '0;
        end
    end
    
    // Output assignments
    assign empty_positions = empty_mask;
    assign empty_count = count_reg;
    assign scan_complete = (state == COMPLETE);
    assign positions_valid = (state == COMPLETE);
    
    // Additional helper outputs for move generation
    logic [4:0] first_empty_position;
    logic       has_empty_positions;
    
    // Find first empty position (priority encoder)
    always_comb begin
        first_empty_position = 5'b11111; // Invalid position
        for (int m = 0; m < 25; m++) begin
            if (empty_mask[m] && first_empty_position == 5'b11111) begin
                first_empty_position = m[4:0];
            end
        end
    end
    
    assign has_empty_positions = (count_reg > 0);
    
    // Generate random position selector for move diversity
    logic [4:0] random_seed;
    logic [4:0] selected_empty_position;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            random_seed <= 5'b10101; // Initial seed
        end else begin
            // Simple LFSR for position selection randomization
            random_seed <= {random_seed[3:0], random_seed[4] ^ random_seed[1]};
        end
    end
    
    // Select a random empty position based on seed
    logic [4:0] target_index;
    logic [4:0] current_index;
    
    always_comb begin
        selected_empty_position = first_empty_position;
        if (has_empty_positions && count_reg > 1) begin
            target_index = random_seed % count_reg;
            current_index = 0;
            
            for (int n = 0; n < 25; n++) begin
                if (empty_mask[n]) begin
                    if (current_index == target_index) begin
                        selected_empty_position = n[4:0];
                    end
                    current_index++;
                end
            end
        end
    end
    
    // Debug and verification outputs
    logic [24:0] position_debug;
    assign position_debug = empty_mask;
    
    // Assertion for verification
    // synthesis translate_off
    always @(posedge clk) begin
        if (state == COMPLETE) begin
            assert (count_reg <= 25) else $error("Empty count exceeds maximum positions");
            assert ((empty_mask & board_state) == 0) else $error("Empty mask conflicts with board state");
        end
    end
    // synthesis translate_on
    
endmodule
