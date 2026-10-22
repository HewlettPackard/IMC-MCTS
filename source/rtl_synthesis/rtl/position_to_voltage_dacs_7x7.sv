// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Position to Voltage DACs for 7x7 Go Board
// Converts digital board positions to analog voltages for memristor crossbar
// Handles 49 positions with proper voltage scaling and timing

module position_to_voltage_dacs_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [97:0] board_state,         // 7x7 board state (98 bits, 2 bits per position)
    input  logic [3:0]  voltage_scale,       // Voltage scaling factor
    input  logic        conversion_start,
    output logic [7:0]  dac_voltages [0:48], // 8-bit DAC outputs for each position (49 total)
    output logic        conversion_complete,
    output logic        voltages_stable,
    
    // DAC control interfaces
    output logic        dac_clk,
    output logic [48:0] dac_enable_mask,     // Enable signals for each DAC (49 bits)
    output logic [7:0]  dac_data_bus,       // Shared data bus for DACs
    output logic [5:0]  dac_address,        // Address for DAC selection (6 bits for 49 DACs)
    output logic        dac_write_enable
);

    // Internal registers
    logic [3:0]  state, next_state;
    logic [5:0]  position_counter;           // Counter for 49 positions
    logic [7:0]  voltage_values [0:48];      // Buffer for 49 voltage values
    logic [48:0] dac_enables;                // Enable signals for 49 DACs
    logic [7:0]  current_dac_data;
    logic [5:0]  current_address;
    logic        write_enable;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam DECODE_BOARD = 4'b0001;
    localparam CALCULATE_VOLTAGES = 4'b0010;
    localparam START_CONVERSION = 4'b0011;
    localparam WRITE_DAC_0_16 = 4'b0100;    // Write first third (0-16)
    localparam WRITE_DAC_17_33 = 4'b0101;   // Write second third (17-33)
    localparam WRITE_DAC_34_48 = 4'b0110;   // Write final third (34-48)
    localparam WAIT_SETTLE = 4'b0111;
    localparam COMPLETE = 4'b1000;
    
    // Voltage mapping constants for 7x7 Go
    localparam [7:0] VOLTAGE_EMPTY = 8'h00;  // 0V for empty positions
    localparam [7:0] VOLTAGE_BLACK = 8'h80;  // Mid-scale for black stones
    localparam [7:0] VOLTAGE_WHITE = 8'hFF;  // Full-scale for white stones
    
    // Board position decoding for 7x7 (49 positions)
    logic [1:0] position_states [0:48];
    
    // Generate array assignments for easier access
    genvar i;
    generate
        for (i = 0; i < 49; i++) begin : pos_decode
            assign position_states[i] = board_state[2*i+1:2*i];
        end
    endgenerate
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            position_counter <= '0;
            current_address <= '0;
            write_enable <= 1'b0;
            dac_enables <= '0;
            // Initialize voltage buffer
            for (int j = 0; j < 49; j++) begin
                voltage_values[j] <= VOLTAGE_EMPTY;
            end
        end else begin
            state <= next_state;
            
            case (state)
                DECODE_BOARD: begin
                    position_counter <= '0;
                    dac_enables <= '0;
                end
                
                CALCULATE_VOLTAGES: begin
                    // Calculate voltages for all 49 positions
                    for (int k = 0; k < 49; k++) begin
                        case (position_states[k])
                            2'b00: voltage_values[k] <= VOLTAGE_EMPTY;  // Empty
                            2'b01: voltage_values[k] <= (VOLTAGE_BLACK * voltage_scale) >> 4; // Black
                            2'b10: voltage_values[k] <= (VOLTAGE_WHITE * voltage_scale) >> 4; // White
                            default: voltage_values[k] <= VOLTAGE_EMPTY;
                        endcase
                    end
                end
                
                START_CONVERSION: begin
                    position_counter <= '0;
                    current_address <= '0;
                    write_enable <= 1'b1;
                    dac_enables <= {49{1'b1}}; // Enable all DACs
                end
                
                WRITE_DAC_0_16: begin
                    if (position_counter <= 16) begin
                        current_address <= position_counter;
                        current_dac_data <= voltage_values[position_counter];
                        position_counter <= position_counter + 1;
                    end
                end
                
                WRITE_DAC_17_33: begin
                    if (position_counter <= 33) begin
                        current_address <= position_counter;
                        current_dac_data <= voltage_values[position_counter];
                        position_counter <= position_counter + 1;
                    end
                end
                
                WRITE_DAC_34_48: begin
                    if (position_counter <= 48) begin
                        current_address <= position_counter;
                        current_dac_data <= voltage_values[position_counter];
                        position_counter <= position_counter + 1;
                    end
                end
                
                WAIT_SETTLE: begin
                    write_enable <= 1'b0;
                    // Wait for DAC outputs to settle
                end
                
                IDLE: begin
                    position_counter <= '0;
                    write_enable <= 1'b0;
                    dac_enables <= '0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        
        case (state)
            IDLE: begin
                if (enable && conversion_start)
                    next_state = DECODE_BOARD;
            end
            
            DECODE_BOARD:
                next_state = CALCULATE_VOLTAGES;
                
            CALCULATE_VOLTAGES:
                next_state = START_CONVERSION;
                
            START_CONVERSION:
                next_state = WRITE_DAC_0_16;
                
            WRITE_DAC_0_16: begin
                if (position_counter > 16)
                    next_state = WRITE_DAC_17_33;
            end
            
            WRITE_DAC_17_33: begin
                if (position_counter > 33)
                    next_state = WRITE_DAC_34_48;
            end
            
            WRITE_DAC_34_48: begin
                if (position_counter > 48)
                    next_state = WAIT_SETTLE;
            end
            
            WAIT_SETTLE:
                next_state = COMPLETE;
                
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // DAC timing and control
    logic [2:0] settle_counter;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            settle_counter <= '0;
        end else begin
            if (state == WAIT_SETTLE) begin
                settle_counter <= settle_counter + 1;
            end else begin
                settle_counter <= '0;
            end
        end
    end
    
    // Voltage stability detection
    logic voltages_stable_internal;
    always_comb begin
        voltages_stable_internal = (state == COMPLETE) || 
                                  (state == WAIT_SETTLE && settle_counter >= 4);
    end
    
    // Output assignments
    assign dac_clk = clk;
    assign dac_enable_mask = dac_enables;
    assign dac_data_bus = current_dac_data;
    assign dac_address = current_address;
    assign dac_write_enable = write_enable;
    assign conversion_complete = (state == COMPLETE);
    assign voltages_stable = voltages_stable_internal;
    
    // Copy voltage values to output array
    genvar m;
    generate
        for (m = 0; m < 49; m++) begin : voltage_assign
            assign dac_voltages[m] = voltage_values[m];
        end
    endgenerate

endmodule
