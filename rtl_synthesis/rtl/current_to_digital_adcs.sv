// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Rollout Unit - Current to Digital ADCs
// 2x2 Board Accelerator Architecture
// ============================================================================

module current_to_digital_adcs (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    input  logic       adc_start,
    input  logic       crossbar_ready,
    input  logic [3:0] adc_data_0,
    input  logic [3:0] adc_data_1,
    input  logic [3:0] adc_data_2,
    input  logic [3:0] adc_data_3,
    input  logic [3:0] conversion_valid,
    
    output logic [3:0] digital_out_0,
    output logic [3:0] digital_out_1,
    output logic [3:0] digital_out_2,
    output logic [3:0] digital_out_3,
    output logic       outputs_valid,
    output logic       conversion_done
);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            digital_out_0    <= 4'h0;
            digital_out_1    <= 4'h0;
            digital_out_2    <= 4'h0;
            digital_out_3    <= 4'h0;
            outputs_valid    <= 1'b0;
            conversion_done  <= 1'b0;
        end else if (enable && adc_start && crossbar_ready) begin
            // Validate and register ADC outputs
            digital_out_0 <= conversion_valid[0] ? adc_data_0 : 4'h0;
            digital_out_1 <= conversion_valid[1] ? adc_data_1 : 4'h0;
            digital_out_2 <= conversion_valid[2] ? adc_data_2 : 4'h0;
            digital_out_3 <= conversion_valid[3] ? adc_data_3 : 4'h0;
            
            // All outputs valid when all conversions are valid
            outputs_valid <= &conversion_valid;
            conversion_done <= 1'b1;
        end else begin
            outputs_valid <= 1'b0;
            conversion_done <= 1'b0;
        end
    end

endmodule
