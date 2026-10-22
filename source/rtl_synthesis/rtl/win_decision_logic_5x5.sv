// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Win Decision Logic for 5x5 Go Board
// Processes ADC outputs to determine game outcome during rollout
// Implements neural network decision logic for win/loss evaluation

module win_decision_logic_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [11:0] neural_outputs [0:24],   // Outputs from ADCs
    input  logic        data_valid,
    input  logic        current_player,          // 0=black, 1=white
    input  logic [49:0] board_state,             // Current board for context (50 bits, 2 bits per position)
    input  logic [7:0]  confidence_threshold,    // Minimum confidence for decision
    output logic        black_wins,              // Black player wins
    output logic        white_wins,              // White player wins
    output logic        game_draw,               // Game is a draw
    output logic        decision_valid,
    output logic        decision_complete,
    
    // Decision confidence and analysis
    output logic [7:0]  win_confidence,          // Confidence in decision (0-255)
    output logic [11:0] black_score,             // Calculated score for black
    output logic [11:0] white_score,             // Calculated score for white
    output logic [4:0]  critical_positions,     // Most important positions
    output logic        low_confidence_warning
);

    // Internal registers
    logic [3:0]  state, next_state;
    logic [4:0]  position_counter;
    logic [11:0] accumulated_scores [0:1];       // [0]=black, [1]=white
    logic [11:0] position_weights [0:24];        // Learned position weights
    logic [11:0] final_black_score, final_white_score;
    logic [7:0]  decision_confidence;
    logic [4:0]  important_positions;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam VALIDATE_INPUTS = 4'b0001;
    localparam CALCULATE_SCORES = 4'b0010;
    localparam APPLY_WEIGHTS = 4'b0011;
    localparam POSITION_ANALYSIS = 4'b0100;
    localparam MAKE_DECISION = 4'b0101;
    localparam CALCULATE_CONFIDENCE = 4'b0110;
    localparam COMPLETE = 4'b0111;
    
    // Position weights initialization (strategic positions for 5x5 Go)
    initial begin
        // Corner positions get highest weights
        position_weights[0]  = 12'h800;  // Top-left corner
        position_weights[4]  = 12'h800;  // Top-right corner  
        position_weights[20] = 12'h800;  // Bottom-left corner
        position_weights[24] = 12'h800;  // Bottom-right corner
        
        // Edge positions get medium weights
        position_weights[1]  = 12'h600;  position_weights[2]  = 12'h400;  position_weights[3]  = 12'h600;
        position_weights[5]  = 12'h600;  position_weights[9]  = 12'h600;
        position_weights[10] = 12'h600;  position_weights[14] = 12'h600;
        position_weights[15] = 12'h600;  position_weights[19] = 12'h600;
        position_weights[21] = 12'h600;  position_weights[22] = 12'h400;  position_weights[23] = 12'h600;
        
        // Center and near-center positions
        position_weights[6]  = 12'h500;  position_weights[7]  = 12'h400;  position_weights[8]  = 12'h500;
        position_weights[11] = 12'h400;  position_weights[12] = 12'h700;  position_weights[13] = 12'h400; // Center is important
        position_weights[16] = 12'h500;  position_weights[17] = 12'h400;  position_weights[18] = 12'h500;
    end
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            position_counter <= '0;
        end else begin
            state <= next_state;
            
            case (state)
                CALCULATE_SCORES, POSITION_ANALYSIS: begin
                    if (position_counter < 24) begin
                        position_counter <= position_counter + 1;
                    end
                end
                
                IDLE: begin
                    position_counter <= '0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        case (state)
            IDLE: if (enable && data_valid) next_state = VALIDATE_INPUTS;
            VALIDATE_INPUTS: next_state = CALCULATE_SCORES;
            CALCULATE_SCORES: if (position_counter == 24) next_state = APPLY_WEIGHTS;
            APPLY_WEIGHTS: next_state = POSITION_ANALYSIS;
            POSITION_ANALYSIS: if (position_counter == 24) next_state = MAKE_DECISION;
            MAKE_DECISION: next_state = CALCULATE_CONFIDENCE;
            CALCULATE_CONFIDENCE: next_state = COMPLETE;
            COMPLETE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end
    
    // Input validation
    logic inputs_valid;
    always_comb begin
        inputs_valid = 1'b1;
        for (int i = 0; i < 25; i++) begin
            if (neural_outputs[i] > 12'hFFF) begin
                inputs_valid = 1'b0;
            end
        end
    end
    
    // Score calculation from neural network outputs
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            accumulated_scores[0] <= '0;  // Black
            accumulated_scores[1] <= '0;  // White
        end else if (state == CALCULATE_SCORES) begin
            if (position_counter == 0) begin
                accumulated_scores[0] <= '0;
                accumulated_scores[1] <= '0;
            end
            
            // Interpret neural outputs as position evaluations
            // Higher values favor the player to move
            logic [11:0] position_value = neural_outputs[position_counter];
            logic [1:0] position_state = board_state[2*position_counter+1:2*position_counter];
            
            case (position_state)
                2'b01: begin // Black stone
                    accumulated_scores[0] <= accumulated_scores[0] + position_value;
                end
                2'b10: begin // White stone
                    accumulated_scores[1] <= accumulated_scores[1] + position_value;
                end
                2'b00: begin // Empty - potential for both players
                    accumulated_scores[0] <= accumulated_scores[0] + (position_value >> 1);
                    accumulated_scores[1] <= accumulated_scores[1] + (position_value >> 1);
                end
            endcase
        end
    end
    
    // Apply strategic position weights
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            final_black_score <= '0;
            final_white_score <= '0;
        end else if (state == APPLY_WEIGHTS) begin
            logic [23:0] weighted_black = 24'b0;
            logic [23:0] weighted_white = 24'b0;
            
            // Apply position weights to accumulated scores
            weighted_black = (accumulated_scores[0] * get_total_weight()) >> 12;
            weighted_white = (accumulated_scores[1] * get_total_weight()) >> 12;
            
            final_black_score <= weighted_black[11:0];
            final_white_score <= weighted_white[11:0];
        end
    end
    
    // Calculate total weight for normalization
    function logic [15:0] get_total_weight();
        logic [15:0] total = 16'b0;
        for (int j = 0; j < 25; j++) begin
            total = total + position_weights[j];
        end
        return total;
    endfunction
    
    // Position analysis for critical areas
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            important_positions <= '0;
        end else if (state == POSITION_ANALYSIS) begin
            // Find positions with highest neural network outputs
            logic [11:0] max_output = 12'b0;
            logic [4:0] max_position = 5'b0;
            
            for (int k = 0; k < 25; k++) begin
                if (neural_outputs[k] > max_output) begin
                    max_output = neural_outputs[k];
                    max_position = k[4:0];
                end
            end
            
            important_positions <= max_position;
        end
    end
    
    // Final decision logic
    logic black_wins_reg, white_wins_reg, game_draw_reg;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            black_wins_reg <= 1'b0;
            white_wins_reg <= 1'b0;
            game_draw_reg <= 1'b0;
        end else if (state == MAKE_DECISION) begin
            logic [11:0] score_diff;
            logic [7:0] draw_threshold = 8'd20; // Threshold for draw decision
            
            if (final_black_score > final_white_score) begin
                score_diff = final_black_score - final_white_score;
                if (score_diff > draw_threshold) begin
                    black_wins_reg <= 1'b1;
                    white_wins_reg <= 1'b0;
                    game_draw_reg <= 1'b0;
                end else begin
                    black_wins_reg <= 1'b0;
                    white_wins_reg <= 1'b0;
                    game_draw_reg <= 1'b1;
                end
            end else if (final_white_score > final_black_score) begin
                score_diff = final_white_score - final_black_score;
                if (score_diff > draw_threshold) begin
                    black_wins_reg <= 1'b0;
                    white_wins_reg <= 1'b1;
                    game_draw_reg <= 1'b0;
                end else begin
                    black_wins_reg <= 1'b0;
                    white_wins_reg <= 1'b0;
                    game_draw_reg <= 1'b1;
                end
            end else begin
                // Exact tie
                black_wins_reg <= 1'b0;
                white_wins_reg <= 1'b0;
                game_draw_reg <= 1'b1;
            end
        end
    end
    
    // Confidence calculation
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            decision_confidence <= '0;
        end else if (state == CALCULATE_CONFIDENCE) begin
            logic [11:0] score_diff;
            logic [11:0] total_score;
            
            score_diff = (final_black_score > final_white_score) ? 
                        (final_black_score - final_white_score) : 
                        (final_white_score - final_black_score);
            
            total_score = final_black_score + final_white_score;
            
            if (total_score > 0) begin
                // Confidence based on score difference relative to total
                decision_confidence <= ((score_diff << 8) / total_score)[7:0];
            end else begin
                decision_confidence <= 8'd128; // Medium confidence for no-score situation
            end
        end
    end
    
    // Output assignments
    assign black_wins = black_wins_reg;
    assign white_wins = white_wins_reg;
    assign game_draw = game_draw_reg;
    assign decision_valid = (state == COMPLETE) && inputs_valid;
    assign decision_complete = (state == COMPLETE);
    assign win_confidence = decision_confidence;
    assign black_score = final_black_score;
    assign white_score = final_white_score;
    assign critical_positions = important_positions;
    assign low_confidence_warning = (decision_confidence < confidence_threshold);
    
    // Additional analysis outputs
    logic score_imbalance;
    logic neural_saturation;
    
    always_comb begin
        score_imbalance = 1'b0;
        neural_saturation = 1'b0;
        
        // Check for extreme score imbalances
        logic [11:0] total_score = final_black_score + final_white_score;
        if (total_score > 0) begin
            logic [11:0] max_score = (final_black_score > final_white_score) ? 
                                   final_black_score : final_white_score;
            score_imbalance = (max_score > (total_score >> 1) + (total_score >> 2)); // >75% of total
        end
        
        // Check for neural network saturation
        for (int m = 0; m < 25; m++) begin
            if (neural_outputs[m] >= 12'hFF0) begin
                neural_saturation = 1'b1;
            end
        end
    end
    
    // Debug outputs
    logic [3:0] debug_state;
    logic [11:0] debug_total_score;
    logic debug_imbalance;
    
    assign debug_state = state;
    assign debug_total_score = final_black_score + final_white_score;
    assign debug_imbalance = score_imbalance;
    
endmodule
