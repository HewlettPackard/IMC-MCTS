// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Child Statistics Access Unit for 5x5 Go Board
// Accesses win/visit statistics for each child node to enable UCB1 calculation
// Scales to handle 25 positions with 4 children each

module child_stats_access_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [6:0]  node_address,        // 7-bit address for 25 positions * 4 children
    input  logic [1:0]  child_index,        // Which child (0-3)
    output logic [15:0] child_wins,         // 16-bit win count
    output logic [15:0] child_visits,       // 16-bit visit count
    output logic        data_valid,
    output logic        access_complete,
    
    // Memory interface for statistics SRAM (14KB for 5x5)
    output logic        stats_mem_en,
    output logic        stats_mem_we,
    output logic [13:0] stats_mem_addr,     // 14-bit address for 14KB
    output logic [31:0] stats_mem_wdata,
    input  logic [31:0] stats_mem_rdata
);

    // Internal registers
    logic [1:0]  state, next_state;
    logic [6:0]  current_node;
    logic [1:0]  current_child;
    logic [13:0] calculated_addr;
    logic [15:0] wins_reg, visits_reg;
    
    // State encoding
    localparam IDLE = 2'b00;
    localparam READ_STATS = 2'b01;
    localparam WAIT_DATA = 2'b10;
    localparam COMPLETE = 2'b11;
    
    // Address calculation for 5x5 board statistics
    // Each node has 4 children, each child has 32-bit data (16-bit wins + 16-bit visits)
    // Base address = node_address * 16 + child_index * 4
    always_comb begin
        calculated_addr = {node_address, 4'b0000} + {child_index, 2'b00};
    end
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            current_node <= '0;
            current_child <= '0;
        end else begin
            state <= next_state;
            if (enable && state == IDLE) begin
                current_node <= node_address;
                current_child <= child_index;
            end
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        case (state)
            IDLE: if (enable) next_state = READ_STATS;
            READ_STATS: next_state = WAIT_DATA;
            WAIT_DATA: next_state = COMPLETE;
            COMPLETE: next_state = IDLE;
        endcase
    end
    
    // Memory interface control
    always_comb begin
        stats_mem_en = (state == READ_STATS);
        stats_mem_we = 1'b0;  // Read only
        stats_mem_addr = calculated_addr;
        stats_mem_wdata = '0;
    end
    
    // Data capture and output
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            wins_reg <= '0;
            visits_reg <= '0;
        end else if (state == WAIT_DATA) begin
            wins_reg <= stats_mem_rdata[31:16];
            visits_reg <= stats_mem_rdata[15:0];
        end
    end
    
    // Output assignments
    assign child_wins = wins_reg;
    assign child_visits = visits_reg;
    assign data_valid = (state == COMPLETE);
    assign access_complete = (state == COMPLETE);
    
endmodule
