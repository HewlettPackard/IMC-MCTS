// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Position to Voltage DACs for 5x5 Go Board
// Converts digital board positions to analog voltages for memristor crossbar
// Handles 25 positions with proper voltage scaling and timing

module position_to_voltage_dacs_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [49:0] board_state,         // 5x5 board state (50 bits total, 2 bits per position)
    input  logic [3:0]  voltage_scale,       // Voltage scaling factor
    input  logic        conversion_start,
    output logic [7:0]  dac_voltages [0:24], // 8-bit DAC outputs for each position
    output logic        conversion_complete,
    output logic        voltages_stable,
    
    // DAC control interfaces
    output logic        dac_clk,
    output logic [24:0] dac_enable_mask,     // Enable signals for each DAC
    output logic [7:0]  dac_data_bus,       // Shared data bus for DACs
    output logic [4:0]  dac_address,        // Address for DAC selection
    output logic        dac_write_enable
);

    // Internal registers
    logic [3:0]  state, next_state;
    logic [4:0]  position_counter;
    logic [7:0]  voltage_values [0:24];
    logic [24:0] dac_enables;
    logic [7:0]  current_dac_data;
    logic [4:0]  current_address;
    logic        write_enable;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam DECODE_BOARD = 4'b0001;
    localparam CALCULATE_VOLTAGES = 4'b0010;
    localparam START_CONVERSION = 4'b0011;
    localparam WRITE_DAC_0_12 = 4'b0100;    // Write first half
    localparam WRITE_DAC_13_24 = 4'b0101;   // Write second half  
    localparam WAIT_SETTLE = 4'b0110;
    localparam COMPLETE = 4'b0111;
    
    // Voltage mapping constants for 5x5 Go
    localparam [7:0] VOLTAGE_EMPTY = 8'h00;  // 0V for empty positions
    localparam [7:0] VOLTAGE_BLACK = 8'h80;  // Mid-scale for black stones
    localparam [7:0] VOLTAGE_WHITE = 8'hFF;  // Full-scale for white stones
    
    // Board position decoding
    logic [1:0] position_states [0:24];
    
    genvar i;
    generate
        for (i = 0; i < 25; i++) begin : pos_decode
            assign position_states[i] = board_state[2*i+1:2*i];
        end
    endgenerate
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            position_counter <= '0;
        end else begin
            state <= next_state;
            
            case (state)
                START_CONVERSION, WRITE_DAC_0_12, WRITE_DAC_13_24: begin
                    if (position_counter < 24) begin
                        position_counter <= position_counter + 1;
                    end else begin
                        position_counter <= '0;
                    end
                end
                
                IDLE: begin
                    position_counter <= '0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        case (state)
            IDLE: if (enable && conversion_start) next_state = DECODE_BOARD;
            DECODE_BOARD: next_state = CALCULATE_VOLTAGES;
            CALCULATE_VOLTAGES: next_state = START_CONVERSION;
            START_CONVERSION: next_state = WRITE_DAC_0_12;
            WRITE_DAC_0_12: if (position_counter == 12) next_state = WRITE_DAC_13_24;
            WRITE_DAC_13_24: if (position_counter == 24) next_state = WAIT_SETTLE;
            WAIT_SETTLE: next_state = COMPLETE;
            COMPLETE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end
    
    // Voltage calculation based on board state
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int j = 0; j < 25; j++) begin
                voltage_values[j] <= VOLTAGE_EMPTY;
            end
        end else if (state == CALCULATE_VOLTAGES) begin
            for (int k = 0; k < 25; k++) begin
                case (position_states[k])
                    2'b00: voltage_values[k] <= VOLTAGE_EMPTY;
                    2'b01: voltage_values[k] <= apply_scaling(VOLTAGE_BLACK, voltage_scale);
                    2'b10: voltage_values[k] <= apply_scaling(VOLTAGE_WHITE, voltage_scale);
                    default: voltage_values[k] <= VOLTAGE_EMPTY;
                endcase
            end
        end
    end
    
    // Voltage scaling function
    function logic [7:0] apply_scaling(input logic [7:0] base_voltage, input logic [3:0] scale);
        logic [11:0] scaled_result;
        scaled_result = (base_voltage * scale) >> 4; // Divide by 16
        return scaled_result[7:0];
    endfunction
    
    // DAC interface control
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_dac_data <= '0;
            current_address <= '0;
            write_enable <= 1'b0;
            dac_enables <= '0;
        end else begin
            case (state)
                WRITE_DAC_0_12: begin
                    if (position_counter <= 12) begin
                        current_dac_data <= voltage_values[position_counter];
                        current_address <= position_counter;
                        write_enable <= 1'b1;
                        dac_enables[position_counter] <= 1'b1;
                    end else begin
                        write_enable <= 1'b0;
                    end
                end
                
                WRITE_DAC_13_24: begin
                    if (position_counter >= 13 && position_counter <= 24) begin
                        current_dac_data <= voltage_values[position_counter];
                        current_address <= position_counter;
                        write_enable <= 1'b1;
                        dac_enables[position_counter] <= 1'b1;
                    end else begin
                        write_enable <= 1'b0;
                    end
                end
                
                WAIT_SETTLE: begin
                    write_enable <= 1'b0;
                    dac_enables <= 25'h1FFFFFF; // Enable all DACs for settling
                end
                
                IDLE: begin
                    write_enable <= 1'b0;
                    dac_enables <= '0;
                end
                
                default: begin
                    write_enable <= 1'b0;
                end
            endcase
        end
    end
    
    // DAC clock generation (slower than system clock for DAC timing)
    logic [2:0] dac_clk_div;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            dac_clk_div <= '0;
        end else begin
            dac_clk_div <= dac_clk_div + 1;
        end
    end
    
    assign dac_clk = dac_clk_div[2]; // Divide by 8
    
    // Output assignments
    always_comb begin
        for (int m = 0; m < 25; m++) begin
            dac_voltages[m] = voltage_values[m];
        end
    end
    
    assign conversion_complete = (state == COMPLETE);
    assign voltages_stable = (state == COMPLETE) || (state == WAIT_SETTLE);
    assign dac_enable_mask = dac_enables;
    assign dac_data_bus = current_dac_data;
    assign dac_address = current_address;
    assign dac_write_enable = write_enable;
    
    // Voltage monitoring and error detection
    logic [7:0] max_voltage, min_voltage;
    logic voltage_range_error;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            max_voltage <= '0;
            min_voltage <= 8'hFF;
        end else if (state == CALCULATE_VOLTAGES) begin
            max_voltage <= '0;
            min_voltage <= 8'hFF;
            
            for (int n = 0; n < 25; n++) begin
                if (voltage_values[n] > max_voltage) begin
                    max_voltage <= voltage_values[n];
                end
                if (voltage_values[n] < min_voltage) begin
                    min_voltage <= voltage_values[n];
                end
            end
        end
    end
    
    assign voltage_range_error = (max_voltage > 8'hF0) || (min_voltage < 8'h05);
    
    // Performance monitoring
    logic [7:0] conversion_cycles;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            conversion_cycles <= '0;
        end else if (state == IDLE) begin
            conversion_cycles <= '0;
        end else if (state != IDLE && state != COMPLETE) begin
            conversion_cycles <= conversion_cycles + 1;
        end
    end
    
    // Debug outputs
    logic [3:0] debug_state;
    logic [4:0] debug_position;
    logic [7:0] debug_cycles;
    
    assign debug_state = state;
    assign debug_position = position_counter;
    assign debug_cycles = conversion_cycles;
    
endmodule
