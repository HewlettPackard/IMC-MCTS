// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Rollout Unit - Win Decision Logic
// 2x2 Board Accelerator Architecture
// ============================================================================

module win_decision_logic (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    input  logic [3:0] nn_output_0,
    input  logic [3:0] nn_output_1,
    input  logic [3:0] nn_output_2,
    input  logic [3:0] nn_output_3,
    input  logic       outputs_valid,
    
    output logic [1:0] game_result,     // 00=draw, 01=player1_win, 10=player2_win, 11=undecided
    output logic [3:0] confidence,
    output logic       decision_valid
);

    parameter logic [3:0] THRESHOLD = 4'h8; // Mid-point threshold

    // Convert NN output to position control (above/below threshold)
    function automatic logic [1:0] threshold_output(logic [3:0] nn_val);
        if (nn_val > THRESHOLD)
            return 2'b01; // Player 1 control
        else if (nn_val < THRESHOLD)
            return 2'b10; // Player 2 control
        else
            return 2'b00; // Neutral/draw
    endfunction

    // Check win pattern
    function automatic logic check_win_pattern(
        logic [1:0] pos0, logic [1:0] pos1, 
        logic [1:0] pos2, logic [1:0] pos3,
        logic [1:0] player
    );
        logic row1, row2, col1, col2, diag1, diag2;
        
        // 2x2 Win patterns:
        row1  = (pos0 == player) && (pos1 == player); // Top row
        row2  = (pos2 == player) && (pos3 == player); // Bottom row
        col1  = (pos0 == player) && (pos2 == player); // Left column
        col2  = (pos1 == player) && (pos3 == player); // Right column
        diag1 = (pos0 == player) && (pos3 == player); // Main diagonal
        diag2 = (pos1 == player) && (pos2 == player); // Anti-diagonal
        
        return row1 || row2 || col1 || col2 || diag1 || diag2;
    endfunction

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            game_result     <= 2'b11; // Undecided
            confidence      <= 4'h0;
            decision_valid  <= 1'b0;
        end else if (enable && outputs_valid) begin
            logic [1:0] pos_control [4];
            logic player1_wins, player2_wins;
            logic [3:0] total_confidence;
            
            // Convert NN outputs to position control
            pos_control[0] = threshold_output(nn_output_0);
            pos_control[1] = threshold_output(nn_output_1);
            pos_control[2] = threshold_output(nn_output_2);
            pos_control[3] = threshold_output(nn_output_3);
            
            // Check win conditions
            player1_wins = check_win_pattern(
                pos_control[0], pos_control[1], pos_control[2], pos_control[3], 2'b01
            );
            player2_wins = check_win_pattern(
                pos_control[0], pos_control[1], pos_control[2], pos_control[3], 2'b10
            );
            
            // Determine game result
            if (player1_wins && !player2_wins)
                game_result <= 2'b01; // Player 1 wins
            else if (player2_wins && !player1_wins)
                game_result <= 2'b10; // Player 2 wins
            else if (!player1_wins && !player2_wins)
                game_result <= 2'b00; // Draw
            else
                game_result <= 2'b11; // Undecided (both win - shouldn't happen)
            
            // Calculate confidence based on NN output strength
            total_confidence = (nn_output_0 > THRESHOLD ? (nn_output_0 - THRESHOLD) : (THRESHOLD - nn_output_0)) +
                              (nn_output_1 > THRESHOLD ? (nn_output_1 - THRESHOLD) : (THRESHOLD - nn_output_1)) +
                              (nn_output_2 > THRESHOLD ? (nn_output_2 - THRESHOLD) : (THRESHOLD - nn_output_2)) +
                              (nn_output_3 > THRESHOLD ? (nn_output_3 - THRESHOLD) : (THRESHOLD - nn_output_3));
            
            confidence <= total_confidence[3:0];
            decision_valid <= 1'b1;
        end else begin
            decision_valid <= 1'b0;
        end
    end

endmodule
