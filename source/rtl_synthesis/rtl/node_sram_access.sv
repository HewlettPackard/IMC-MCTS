// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// IMC-MCTS Selection Unit - Node SRAM Access Module
// 5x5 Board Configuration
// Manages memory access operations for MCTS tree nodes with enhanced caching

module node_sram_access_5x5 #(
    parameter ADDRESS_WIDTH = 18,
    parameter DATA_WIDTH = 64,
    parameter CACHE_SIZE = 32,
    parameter BURST_LENGTH = 8
)(
    input  logic                        clk,
    input  logic                        rst_n,
    
    // Control Interface
    input  logic                        access_enable,
    input  logic                        read_enable,
    input  logic                        write_enable,
    input  logic [ADDRESS_WIDTH-1:0]   node_address,
    input  logic [DATA_WIDTH-1:0]      write_data,
    input  logic [1:0]                 access_mode,
    
    // SRAM Interface
    output logic [ADDRESS_WIDTH-1:0]   sram_address,
    output logic                        sram_chip_enable,
    output logic                        sram_write_enable,
    output logic                        sram_output_enable,
    inout  logic [DATA_WIDTH-1:0]      sram_data,
    
    // Enhanced Cache Interface
    input  logic [31:0]                cache_hit_mask,
    input  logic [DATA_WIDTH-1:0]      cache_data [CACHE_SIZE-1:0],
    output logic [4:0]                 cache_index,
    output logic                        cache_write_enable,
    output logic                        cache_prefetch_enable,
    
    // Output Interface
    output logic [DATA_WIDTH-1:0]      read_data,
    output logic                        access_complete,
    output logic                        cache_hit,
    output logic                        memory_busy,
    output logic [2:0]                 performance_mode
);

    // Internal signals
    logic [DATA_WIDTH-1:0] sram_data_out;
    logic [DATA_WIDTH-1:0] sram_data_in;
    logic sram_data_oe;
    
    // Enhanced state machine for 5x5
    typedef enum logic [3:0] {
        IDLE,
        CACHE_CHECK,
        SRAM_ACCESS,
        BURST_READ,
        PREFETCH,
        BANK_SWITCH,
        COMPLETE
    } access_state_t;
    
    access_state_t current_state, next_state;
    
    // Burst and prefetch control
    logic [3:0] burst_counter;
    logic [4:0] prefetch_counter;
    
    // Cache hit detection for 25 positions (enhanced)
    logic cache_hit_detected;
    logic [4:0] hit_cache_index;
    logic [2:0] cache_performance;
    
    always_comb begin
        cache_hit_detected = |cache_hit_mask[24:0];
        hit_cache_index = 5'h0;
        cache_performance = 3'h0;
        
        // Priority encoder for cache hits
        for (int i = 0; i < 25; i++) begin
            if (cache_hit_mask[i]) begin
                hit_cache_index = i[4:0];
                cache_performance = cache_performance + 1'b1;
                break;
            end
        end
    end
    
    // State machine sequential logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_state <= IDLE;
            burst_counter <= 4'h0;
            prefetch_counter <= 5'h0;
        end else begin
            current_state <= next_state;
            
            case (current_state)
                BURST_READ: begin
                    if (burst_counter < BURST_LENGTH) begin
                        burst_counter <= burst_counter + 1'b1;
                    end
                end
                
                PREFETCH: begin
                    if (prefetch_counter < 5'd16) begin
                        prefetch_counter <= prefetch_counter + 1'b1;
                    end
                end
                
                default: begin
                    burst_counter <= 4'h0;
                    prefetch_counter <= 5'h0;
                end
            endcase
        end
    end
    
    // State machine combinational logic
    always_comb begin
        next_state = current_state;
        case (current_state)
            IDLE: begin
                if (access_enable) begin
                    next_state = CACHE_CHECK;
                end
            end
            
            CACHE_CHECK: begin
                if (cache_hit_detected && read_enable) begin
                    next_state = COMPLETE;
                end else begin
                    next_state = SRAM_ACCESS;
                end
            end
            
            SRAM_ACCESS: begin
                case (access_mode)
                    2'b00: next_state = COMPLETE; // Single access
                    2'b01: next_state = BURST_READ; // Burst mode
                    2'b10: next_state = PREFETCH; // Prefetch mode
                    2'b11: next_state = BANK_SWITCH; // Bank mode
                endcase
            end
            
            BURST_READ: begin
                if (burst_counter >= BURST_LENGTH) next_state = COMPLETE;
            end
            
            PREFETCH: begin
                if (prefetch_counter >= 5'd16) next_state = COMPLETE;
            end
            
            BANK_SWITCH: next_state = COMPLETE;
            
            COMPLETE: next_state = IDLE;
        endcase
    end
    
    // SRAM control signals
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sram_address <= '0;
            sram_chip_enable <= 1'b0;
            sram_write_enable <= 1'b0;
            sram_output_enable <= 1'b0;
            sram_data_oe <= 1'b0;
        end else begin
            case (current_state)
                SRAM_ACCESS, BURST_READ, PREFETCH: begin
                    sram_address <= node_address + burst_counter;
                    sram_chip_enable <= 1'b1;
                    sram_write_enable <= write_enable && (current_state == SRAM_ACCESS);
                    sram_output_enable <= read_enable;
                    sram_data_oe <= write_enable && (current_state == SRAM_ACCESS);
                end
                
                default: begin
                    sram_chip_enable <= 1'b0;
                    sram_write_enable <= 1'b0;
                    sram_output_enable <= 1'b0;
                    sram_data_oe <= 1'b0;
                end
            endcase
        end
    end
    
    // Bidirectional data handling
    assign sram_data = sram_data_oe ? write_data : 'z;
    assign sram_data_in = sram_data;
    
    // Output data selection with enhanced logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            read_data <= '0;
        end else begin
            if (current_state == CACHE_CHECK && cache_hit_detected) begin
                read_data <= cache_data[hit_cache_index];
            end else if ((current_state == SRAM_ACCESS || current_state == BURST_READ) && read_enable) begin
                read_data <= sram_data_in;
            end
        end
    end
    
    // Enhanced cache control
    assign cache_index = hit_cache_index;
    assign cache_write_enable = ((current_state == SRAM_ACCESS) || (current_state == BURST_READ)) && read_enable;
    assign cache_prefetch_enable = (current_state == PREFETCH);
    
    // Status outputs
    assign access_complete = (current_state == COMPLETE);
    assign cache_hit = cache_hit_detected && (current_state == CACHE_CHECK);
    assign memory_busy = (current_state != IDLE) && (current_state != COMPLETE);
    assign performance_mode = cache_performance;

endmodule
