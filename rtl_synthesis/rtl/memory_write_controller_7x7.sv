// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Memory Write Controller for 7x7 Go Board
// Manages write operations to node SRAM based on updated statistics

module memory_write_controller_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [6:0]  node_id,
    input  logic [15:0] updated_visits,
    input  logic [15:0] updated_wins,
    input  logic        write_enable_in,
    
    // Memory interface
    output logic [13:0] mem_address,
    output logic [31:0] mem_write_data,
    output logic        mem_write_enable,
    output logic        mem_chip_select,
    
    // Control outputs
    output logic        write_complete,
    output logic        write_error
);

    // Internal registers
    logic [1:0]  write_state;
    logic [6:0]  stored_node_id;
    logic [15:0] stored_visits;
    logic [15:0] stored_wins;
    logic        write_pending;
    
    // State encoding
    localparam IDLE       = 2'b00;
    localparam WRITE_PREP = 2'b01;
    localparam WRITE_EXEC = 2'b10;
    localparam WRITE_DONE = 2'b11;
    
    // Node ID validation (0-48 for 7x7 board)
    logic node_id_valid;
    assign node_id_valid = (node_id <= 7'd48);
    
    // Memory address calculation
    // Each node requires 4 bytes (32 bits): 16 bits for visits + 16 bits for wins
    // Address = node_id * 4 (word-aligned addressing)
    logic [13:0] calculated_address;
    assign calculated_address = {7'b0000000, node_id} << 2;
    
    // Data packing: [31:16] = wins, [15:0] = visits
    logic [31:0] packed_data;
    assign packed_data = {stored_wins, stored_visits};
    
    // State machine and control logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            write_state <= IDLE;
            stored_node_id <= 7'b0;
            stored_visits <= 16'b0;
            stored_wins <= 16'b0;
            write_pending <= 1'b0;
            mem_address <= 14'b0;
            mem_write_data <= 32'b0;
            mem_write_enable <= 1'b0;
            mem_chip_select <= 1'b0;
            write_complete <= 1'b0;
            write_error <= 1'b0;
        end else begin
            case (write_state)
                IDLE: begin
                    write_complete <= 1'b0;
                    write_error <= 1'b0;
                    mem_write_enable <= 1'b0;
                    mem_chip_select <= 1'b0;
                    
                    if (enable && write_enable_in) begin
                        if (node_id_valid) begin
                            stored_node_id <= node_id;
                            stored_visits <= updated_visits;
                            stored_wins <= updated_wins;
                            write_pending <= 1'b1;
                            write_state <= WRITE_PREP;
                        end else begin
                            write_error <= 1'b1;
                            write_state <= WRITE_DONE;
                        end
                    end
                end
                
                WRITE_PREP: begin
                    // Prepare memory interface signals
                    mem_address <= calculated_address;
                    mem_write_data <= packed_data;
                    mem_chip_select <= 1'b1;
                    write_state <= WRITE_EXEC;
                end
                
                WRITE_EXEC: begin
                    // Execute write operation
                    mem_write_enable <= 1'b1;
                    write_state <= WRITE_DONE;
                end
                
                WRITE_DONE: begin
                    // Complete write operation
                    mem_write_enable <= 1'b0;
                    mem_chip_select <= 1'b0;
                    write_pending <= 1'b0;
                    write_complete <= 1'b1;
                    
                    if (!write_enable_in) begin
                        write_state <= IDLE;
                    end
                end
                
                default: begin
                    write_state <= IDLE;
                end
            endcase
        end
    end
    
    // Additional safety checks
    always_comb begin
        // Ensure address is within valid range for 7x7 board
        // Maximum address: 48 * 4 = 192 (0xC0)
        if (calculated_address > 14'd192) begin
            // Address out of bounds - this shouldn't happen with valid node_id
            assert(1'b0) else $error("Memory address out of bounds: %d", calculated_address);
        end
    end
    
    // Performance monitoring
    logic [15:0] write_count;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            write_count <= 16'b0;
        end else if (write_state == WRITE_DONE && write_complete) begin
            write_count <= write_count + 1'b1;
        end
    end

endmodule
