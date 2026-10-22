// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Current to Digital ADCs for 7x7 Go Board
// Converts analog current outputs from memristor crossbar to digital values
// Handles 49 parallel ADC channels for 7x7 game state processing

module current_to_digital_adcs_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic        analog_currents [0:48],      // 49 analog current inputs from crossbar
    input  logic        ref_current_high,            // Reference current for "stone present" threshold
    input  logic        ref_current_low,             // Reference current for "empty position" threshold
    input  logic        conversion_start,
    output logic [97:0] digital_positions,           // 98-bit output (2 bits per position, 49 positions)
    output logic        conversion_complete,
    output logic        adc_valid,
    output logic [1:0]  position_states [0:48],      // 2D array of 2-bit position states
    
    // ADC control and status
    output logic [5:0]  conversion_progress,         // Number of ADCs completed
    output logic        all_adcs_ready,
    output logic [48:0] adc_error_mask               // Error flags for each ADC channel
);

    // Internal registers
    logic [2:0]  state, next_state;
    logic [5:0]  adc_counter;
    logic [1:0]  conversion_states [0:48];           // Internal state buffer for 49 positions
    logic [48:0] adc_complete_mask;                  // Track completion of each ADC
    logic [48:0] adc_error_flags;
    logic [7:0]  conversion_delay_counter;
    
    // State encoding
    localparam IDLE = 3'b000;
    localparam START_CONVERSION = 3'b001;
    localparam PARALLEL_CONVERT = 3'b010;
    localparam WAIT_SETTLE = 3'b011;
    localparam VALIDATE_RESULTS = 3'b100;
    localparam COMPLETE = 3'b101;
    
    // ADC conversion parameters
    localparam CONVERSION_CYCLES = 8'd32;           // ADC conversion time
    localparam SETTLE_CYCLES = 8'd8;                // Settlement time
    
    // Current level thresholds (simplified digital representation)
    localparam [7:0] THRESHOLD_LOW = 8'h40;         // Empty position threshold
    localparam [7:0] THRESHOLD_HIGH = 8'hC0;        // Stone present threshold
    
    // Simulated current-to-digital conversion (would be analog in real implementation)
    logic [7:0] digital_currents [0:48];            // Digitized current values
    
    // Current digitization (simplified model for synthesis)
    genvar i;
    generate
        for (i = 0; i < 49; i++) begin : current_digitize
            // In real implementation, this would be analog ADC cores
            // For synthesis, we model as simple threshold detection
            always_ff @(posedge clk or negedge rst_n) begin
                if (!rst_n) begin
                    digital_currents[i] <= 8'h00;
                end else if (state == PARALLEL_CONVERT) begin
                    // Simplified current-to-digital conversion
                    // In real design, this would interface with analog ADC blocks
                    digital_currents[i] <= {6'h20, analog_currents[i], 1'b0}; // Mock conversion
                end
            end
        end
    endgenerate
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            adc_counter <= '0;
            conversion_delay_counter <= '0;
            adc_complete_mask <= '0;
            adc_error_flags <= '0;
            // Initialize conversion states
            for (int j = 0; j < 49; j++) begin
                conversion_states[j] <= 2'b00;
            end
        end else begin
            state <= next_state;
            
            case (state)
                START_CONVERSION: begin
                    adc_counter <= '0;
                    conversion_delay_counter <= '0;
                    adc_complete_mask <= '0;
                    adc_error_flags <= '0;
                end
                
                PARALLEL_CONVERT: begin
                    if (conversion_delay_counter < CONVERSION_CYCLES) begin
                        conversion_delay_counter <= conversion_delay_counter + 1;
                    end else begin
                        // Perform parallel ADC conversion for all 49 channels
                        for (int k = 0; k < 49; k++) begin
                            // Convert current level to position state
                            if (digital_currents[k] < THRESHOLD_LOW) begin
                                conversion_states[k] <= 2'b00; // Empty position
                            end else if (digital_currents[k] < THRESHOLD_HIGH) begin
                                conversion_states[k] <= 2'b01; // Black stone (medium current)
                            end else begin
                                conversion_states[k] <= 2'b10; // White stone (high current)
                            end
                            
                            // Mark ADC as complete
                            adc_complete_mask[k] <= 1'b1;
                        end
                    end
                end
                
                WAIT_SETTLE: begin
                    if (conversion_delay_counter < SETTLE_CYCLES) begin
                        conversion_delay_counter <= conversion_delay_counter + 1;
                    end
                end
                
                VALIDATE_RESULTS: begin
                    // Validate conversion results and check for errors
                    for (int m = 0; m < 49; m++) begin
                        // Simple error checking (in real design, would check ADC status)
                        if (conversion_states[m] == 2'b11) begin
                            adc_error_flags[m] <= 1'b1; // Invalid state
                            conversion_states[m] <= 2'b00; // Default to empty
                        end else begin
                            adc_error_flags[m] <= 1'b0;
                        end
                    end
                end
                
                IDLE: begin
                    conversion_delay_counter <= '0;
                    adc_counter <= '0;
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
                    next_state = START_CONVERSION;
            end
            
            START_CONVERSION:
                next_state = PARALLEL_CONVERT;
                
            PARALLEL_CONVERT: begin
                if (conversion_delay_counter >= CONVERSION_CYCLES)
                    next_state = WAIT_SETTLE;
            end
            
            WAIT_SETTLE: begin
                if (conversion_delay_counter >= SETTLE_CYCLES)
                    next_state = VALIDATE_RESULTS;
            end
            
            VALIDATE_RESULTS:
                next_state = COMPLETE;
                
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // Pack conversion results into output format
    always_comb begin
        digital_positions = '0;
        for (int n = 0; n < 49; n++) begin
            digital_positions[2*n+1:2*n] = conversion_states[n];
        end
    end
    
    // Count completed ADCs
    logic [5:0] completed_adcs;
    always_comb begin
        completed_adcs = '0;
        for (int p = 0; p < 49; p++) begin
            if (adc_complete_mask[p])
                completed_adcs++;
        end
    end
    
    // Error detection and reporting
    logic has_conversion_errors;
    always_comb begin
        has_conversion_errors = |adc_error_flags;
    end
    
    // Output assignments
    assign conversion_complete = (state == COMPLETE);
    assign adc_valid = (state == COMPLETE) && !has_conversion_errors;
    assign conversion_progress = completed_adcs;
    assign all_adcs_ready = (completed_adcs == 6'd49);
    assign adc_error_mask = adc_error_flags;
    
    // Copy internal states to output array
    genvar q;
    generate
        for (q = 0; q < 49; q++) begin : state_assign
            assign position_states[q] = conversion_states[q];
        end
    endgenerate

endmodule
