// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Backpropagation Unit - Statistics Updater
// 2x2 Board Accelerator Architecture
// ============================================================================

module statistics_updater (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    input  logic [7:0] current_wins_0,
    input  logic [7:0] current_visits_0,
    input  logic [7:0] current_wins_1,
    input  logic [7:0] current_visits_1,
    input  logic [7:0] current_wins_2,
    input  logic [7:0] current_visits_2,
    input  logic [1:0] rollout_result,   // 00=draw, 01=win, 10=loss
    input  logic [2:0] update_mask,
    
    output logic [7:0] new_wins_0,
    output logic [7:0] new_visits_0,
    output logic [7:0] new_wins_1,
    output logic [7:0] new_visits_1,
    output logic [7:0] new_wins_2,
    output logic [7:0] new_visits_2,
    output logic       update_done
);

    // Calculate win increment based on rollout result
    function automatic logic [7:0] get_win_increment(logic [1:0] result);
        case (result)
            2'b01: return 8'h01; // Win: +1
            2'b10: return 8'h00; // Loss: +0
            2'b00: return 8'h01; // Draw: +0.5 (simplified to +1 for integer math)
            default: return 8'h00;
        endcase
    endfunction

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            new_wins_0   <= 8'h0;
            new_visits_0 <= 8'h0;
            new_wins_1   <= 8'h0;
            new_visits_1 <= 8'h0;
            new_wins_2   <= 8'h0;
            new_visits_2 <= 8'h0;
            update_done  <= 1'b0;
        end else if (enable) begin
            logic [7:0] win_increment;
            
            win_increment = get_win_increment(rollout_result);
            
            // Update node 0 statistics
            if (update_mask[0]) begin
                new_visits_0 <= current_visits_0 + 8'h01; // Always increment visits
                new_wins_0   <= current_wins_0 + win_increment;
            end else begin
                new_visits_0 <= current_visits_0;
                new_wins_0   <= current_wins_0;
            end
            
            // Update node 1 statistics
            if (update_mask[1]) begin
                new_visits_1 <= current_visits_1 + 8'h01;
                new_wins_1   <= current_wins_1 + win_increment;
            end else begin
                new_visits_1 <= current_visits_1;
                new_wins_1   <= current_wins_1;
            end
            
            // Update node 2 statistics
            if (update_mask[2]) begin
                new_visits_2 <= current_visits_2 + 8'h01;
                new_wins_2   <= current_wins_2 + win_increment;
            end else begin
                new_visits_2 <= current_visits_2;
                new_wins_2   <= current_wins_2;
            end
            
            update_done <= 1'b1;
        end else begin
            update_done <= 1'b0;
        end
    end

endmodule
