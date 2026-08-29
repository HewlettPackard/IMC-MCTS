// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Node SRAM Access for 7x7 Go Board
// Manages memory read/write operations for MCTS tree nodes
// Supports 16-bit addressing for large tree structures

module node_sram_access_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [15:0] node_address,        // 16-bit node address for large trees
    input  logic        read_enable,
    input  logic        write_enable,
    input  logic [127:0] write_data,         // 128-bit node data (visit count, win count, UCB1, etc.)
    output logic [127:0] read_data,          // 128-bit read data
    output logic        data_valid,
    output logic        operation_complete,
    output logic        memory_ready,
    
    // SRAM interface signals
    output logic        sram_clk,
    output logic        sram_ce_n,           // Chip enable (active low)
    output logic        sram_we_n,           // Write enable (active low)  
    output logic        sram_oe_n,           // Output enable (active low)
    output logic [15:0] sram_addr,           // SRAM address bus
    inout  logic [31:0] sram_data,           // SRAM data bus (32-bit width)
    output logic [3:0]  sram_be_n            // Byte enables (active low)
);

    // Internal registers
    logic [2:0]   state, next_state;
    logic [127:0] data_buffer;
    logic [1:0]   burst_counter;             // For 128-bit data over 32-bit bus
    logic [15:0]  address_reg;
    logic [31:0]  sram_data_out;
    logic [31:0]  sram_data_in;
    logic         sram_data_oe;
    
    // State encoding for 7x7 operations
    localparam IDLE = 3'b000;
    localparam READ_SETUP = 3'b001;
    localparam READ_BURST = 3'b010;
    localparam WRITE_SETUP = 3'b011;
    localparam WRITE_BURST = 3'b100;
    localparam COMPLETE = 3'b101;
    
    // SRAM timing parameters (adjusted for 7x7 complexity)
    localparam SETUP_CYCLES = 2;
    localparam ACCESS_CYCLES = 3;
    
    // Bidirectional data bus control
    assign sram_data = sram_data_oe ? sram_data_out : 32'hZ;
    assign sram_data_in = sram_data;
    
    // SRAM control signals
    assign sram_clk = clk;
    assign sram_addr = address_reg;
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            burst_counter <= '0;
            address_reg <= '0;
            data_buffer <= '0;
        end else begin
            state <= next_state;
            
            case (state)
                READ_SETUP: begin
                    address_reg <= node_address;
                    burst_counter <= '0;
                end
                
                READ_BURST: begin
                    if (burst_counter < 3) begin
                        data_buffer[32*(burst_counter+1)-1:32*burst_counter] <= sram_data_in;
                        burst_counter <= burst_counter + 1;
                        address_reg <= address_reg + 1;
                    end
                end
                
                WRITE_SETUP: begin
                    address_reg <= node_address;
                    burst_counter <= '0;
                    data_buffer <= write_data;
                end
                
                WRITE_BURST: begin
                    if (burst_counter < 3) begin
                        burst_counter <= burst_counter + 1;
                        address_reg <= address_reg + 1;
                    end
                end
                
                IDLE: begin
                    burst_counter <= '0;
                end
            endcase
        end
    end
    
    // Next state logic optimized for 7x7 tree access patterns
    always_comb begin
        next_state = state;
        
        case (state)
            IDLE: begin
                if (enable) begin
                    if (read_enable)
                        next_state = READ_SETUP;
                    else if (write_enable)
                        next_state = WRITE_SETUP;
                end
            end
            
            READ_SETUP:
                next_state = READ_BURST;
                
            READ_BURST: begin
                if (burst_counter >= 3)
                    next_state = COMPLETE;
            end
            
            WRITE_SETUP:
                next_state = WRITE_BURST;
                
            WRITE_BURST: begin
                if (burst_counter >= 3)
                    next_state = COMPLETE;
            end
            
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // SRAM control signal generation
    always_comb begin
        sram_ce_n = 1'b1;
        sram_we_n = 1'b1;
        sram_oe_n = 1'b1;
        sram_be_n = 4'hF;
        sram_data_oe = 1'b0;
        sram_data_out = 32'h0;
        
        case (state)
            READ_SETUP, READ_BURST: begin
                sram_ce_n = 1'b0;
                sram_oe_n = 1'b0;
                sram_be_n = 4'h0;  // Enable all bytes
            end
            
            WRITE_SETUP, WRITE_BURST: begin
                sram_ce_n = 1'b0;
                sram_we_n = 1'b0;
                sram_be_n = 4'h0;  // Enable all bytes
                sram_data_oe = 1'b1;
                sram_data_out = data_buffer[32*(burst_counter+1)-1:32*burst_counter];
            end
        endcase
    end
    
    // Output assignments
    assign read_data = data_buffer;
    assign data_valid = (state == COMPLETE);
    assign operation_complete = (state == COMPLETE);
    assign memory_ready = (state == IDLE);

endmodule
