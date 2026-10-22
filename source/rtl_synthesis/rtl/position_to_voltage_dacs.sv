// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Rollout Unit - Position to Voltage DACs
// 2x2 Board Accelerator Architecture
// ============================================================================

module position_to_voltage_dacs (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    input  logic [1:0] position_0,
    input  logic [1:0] position_1,
    input  logic [1:0] position_2,
    input  logic [1:0] position_3,
    input  logic       dac_enable,
    
    output logic [1:0] dac_code_0,
    output logic [1:0] dac_code_1,
    output logic [1:0] dac_code_2,
    output logic [1:0] dac_code_3,
    output logic       conversion_done
);

    // Map position states to DAC codes
    function automatic logic [1:0] pos_to_dac_code(logic [1:0] pos_state);
        case (pos_state)
            2'b00: return 2'b00; // Empty -> 0V
            2'b01: return 2'b01; // Player 1 -> +V
            2'b10: return 2'b10; // Player 2 -> -V
            2'b11: return 2'b00; // Invalid -> 0V
            default: return 2'b00;
        endcase
    endfunction

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            dac_code_0       <= 2'h0;
            dac_code_1       <= 2'h0;
            dac_code_2       <= 2'h0;
            dac_code_3       <= 2'h0;
            conversion_done  <= 1'b0;
        end else if (enable && dac_enable) begin
            // Convert positions to DAC codes
            dac_code_0 <= pos_to_dac_code(position_0);
            dac_code_1 <= pos_to_dac_code(position_1);
            dac_code_2 <= pos_to_dac_code(position_2);
            dac_code_3 <= pos_to_dac_code(position_3);
            conversion_done <= 1'b1;
        end else begin
            conversion_done <= 1'b0;
        end
    end

endmodule
