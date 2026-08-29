// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Expansion Unit - Empty Position Detector
// 2x2 Board Accelerator Architecture
// ============================================================================

module empty_position_detector (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    input  logic [1:0] position_0,
    input  logic [1:0] position_1,
    input  logic [1:0] position_2,
    input  logic [1:0] position_3,
    
    output logic [3:0] empty_mask,
    output logic [2:0] empty_count,
    output logic       detection_valid
);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            empty_mask       <= 4'h0;
            empty_count      <= 3'h0;
            detection_valid  <= 1'b0;
        end else if (enable) begin
            // Check each position for empty state (2'b00)
            empty_mask[0] <= (position_0 == 2'b00);
            empty_mask[1] <= (position_1 == 2'b00);
            empty_mask[2] <= (position_2 == 2'b00);
            empty_mask[3] <= (position_3 == 2'b00);
            
            // Count empty positions
            empty_count <= (position_0 == 2'b00) + 
                          (position_1 == 2'b00) + 
                          (position_2 == 2'b00) + 
                          (position_3 == 2'b00);
            
            detection_valid <= 1'b1;
        end else begin
            detection_valid <= 1'b0;
        end
    end

endmodule
