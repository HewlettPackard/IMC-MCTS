// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Selection Unit - Output Multiplexer
// 2x2 Board Accelerator Architecture
// ============================================================================

module output_multiplexer (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [31:0] child_data_0,
    input  logic [31:0] child_data_1,
    input  logic [31:0] child_data_2,
    input  logic [31:0] child_data_3,
    input  logic [1:0]  select,
    input  logic        data_valid,
    
    output logic [31:0] selected_data,
    output logic        output_valid
);

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            selected_data <= 32'h0;
            output_valid  <= 1'b0;
        end else if (enable && data_valid) begin
            // 4:1 Multiplexer based on select signal
            case (select)
                2'h0: selected_data <= child_data_0;
                2'h1: selected_data <= child_data_1;
                2'h2: selected_data <= child_data_2;
                2'h3: selected_data <= child_data_3;
                default: selected_data <= 32'h0;
            endcase
            output_valid <= 1'b1;
        end else begin
            output_valid <= 1'b0;
        end
    end

endmodule
