// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Selection Unit - Child Statistics Access
// 2x2 Board Accelerator Architecture
// ============================================================================

module child_stats_access (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    input  logic [3:0] child_addr_0,
    input  logic [3:0] child_addr_1,
    input  logic [3:0] child_addr_2,
    input  logic [3:0] child_addr_3,
    input  logic [63:0] stats_read_data,  // 4x16-bit entries
    input  logic       read_valid,
    
    output logic [7:0] child_0_wins,
    output logic [7:0] child_0_visits,
    output logic [7:0] child_1_wins,
    output logic [7:0] child_1_visits,
    output logic [7:0] child_2_wins,
    output logic [7:0] child_2_visits,
    output logic [7:0] child_3_wins,
    output logic [7:0] child_3_visits,
    output logic       stats_valid
);

    // Extract statistics from packed memory format
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            child_0_wins  <= 8'h0;
            child_0_visits <= 8'h0;
            child_1_wins  <= 8'h0;
            child_1_visits <= 8'h0;
            child_2_wins  <= 8'h0;
            child_2_visits <= 8'h0;
            child_3_wins  <= 8'h0;
            child_3_visits <= 8'h0;
            stats_valid   <= 1'b0;
        end else if (enable && read_valid) begin
            // Unpack statistics data (16 bits per child: 8-bit wins + 8-bit visits)
            {child_0_visits, child_0_wins} <= stats_read_data[15:0];
            {child_1_visits, child_1_wins} <= stats_read_data[31:16];
            {child_2_visits, child_2_wins} <= stats_read_data[47:32];
            {child_3_visits, child_3_wins} <= stats_read_data[63:48];
            stats_valid <= 1'b1;
        end else begin
            stats_valid <= 1'b0;
        end
    end

endmodule
