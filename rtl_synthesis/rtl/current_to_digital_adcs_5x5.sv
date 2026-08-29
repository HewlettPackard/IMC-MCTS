// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Current to Digital ADCs for 5x5 Go Board
// Converts analog currents from memristor crossbar to digital values
// Handles 25 output channels with proper timing and calibration

module current_to_digital_adcs_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic        conversion_start,
    input  logic [7:0]  analog_currents [0:24],  // Analog current inputs (simulated as digital)
    input  logic [3:0]  adc_resolution,          // ADC resolution setting (8-12 bits)
    input  logic [7:0]  reference_current,       // Reference current for calibration
    output logic [11:0] digital_outputs [0:24],  // 12-bit digital outputs
    output logic [24:0] conversion_done,         // Per-channel conversion complete flags
    output logic        all_conversions_done,
    output logic        data_valid,
    
    // ADC control interface
    output logic        adc_clk,
    output logic [24:0] adc_enable_mask,
    output logic [4:0]  adc_channel_select,
    output logic        sample_hold,
    
    // Calibration and monitoring
    input  logic        calibration_mode,
    output logic [11:0] calibration_offset [0:24],
    output logic        calibration_complete,
    output logic        conversion_error
);

    // Internal registers
    logic [3:0]  state, next_state;
    logic [4:0]  channel_counter;
    logic [7:0]  conversion_timer;
    logic [11:0] adc_results [0:24];
    logic [24:0] done_flags;
    logic [11:0] cal_offsets [0:24];
    logic        cal_done;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam CALIBRATE = 4'b0001;
    localparam SETUP_CONVERSION = 4'b0010;
    localparam SAMPLE_INPUTS = 4'b0011;
    localparam CONVERT_CH_0_12 = 4'b0100;   // Convert first half
    localparam CONVERT_CH_13_24 = 4'b0101;  // Convert second half
    localparam APPLY_CALIBRATION = 4'b0110;
    localparam VALIDATE_RESULTS = 4'b0111;
    localparam COMPLETE = 4'b1000;
    
    // ADC timing parameters
    localparam [7:0] SAMPLE_TIME = 8'd5;     // Sample and hold time
    localparam [7:0] CONVERSION_TIME = 8'd20; // Per-channel conversion time
    localparam [7:0] SETTLE_TIME = 8'd3;     // Settling time between channels
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            channel_counter <= '0;
            conversion_timer <= '0;
        end else begin
            state <= next_state;
            
            case (state)
                SAMPLE_INPUTS, CONVERT_CH_0_12, CONVERT_CH_13_24: begin
                    conversion_timer <= conversion_timer + 1;
                end
                
                SETUP_CONVERSION: begin
                    conversion_timer <= '0;
                    channel_counter <= '0;
                end
                
                CONVERT_CH_0_12: begin
                    if (conversion_timer >= CONVERSION_TIME && channel_counter < 12) begin
                        channel_counter <= channel_counter + 1;
                        conversion_timer <= '0;
                    end
                end
                
                CONVERT_CH_13_24: begin
                    if (conversion_timer >= CONVERSION_TIME && channel_counter < 24) begin
                        channel_counter <= channel_counter + 1;
                        conversion_timer <= '0;
                    end
                end
                
                IDLE: begin
                    channel_counter <= '0;
                    conversion_timer <= '0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        case (state)
            IDLE: begin
                if (calibration_mode && !cal_done) next_state = CALIBRATE;
                else if (enable && conversion_start) next_state = SETUP_CONVERSION;
            end
            CALIBRATE: if (channel_counter == 24) next_state = IDLE;
            SETUP_CONVERSION: next_state = SAMPLE_INPUTS;
            SAMPLE_INPUTS: if (conversion_timer >= SAMPLE_TIME) next_state = CONVERT_CH_0_12;
            CONVERT_CH_0_12: if (channel_counter == 12) next_state = CONVERT_CH_13_24;
            CONVERT_CH_13_24: if (channel_counter == 24) next_state = APPLY_CALIBRATION;
            APPLY_CALIBRATION: next_state = VALIDATE_RESULTS;
            VALIDATE_RESULTS: next_state = COMPLETE;
            COMPLETE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end
    
    // Calibration process
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < 25; i++) begin
                cal_offsets[i] <= '0;
            end
            cal_done <= 1'b0;
        end else if (state == CALIBRATE) begin
            // Measure offset with zero input for each channel
            if (channel_counter < 25) begin
                cal_offsets[channel_counter] <= perform_adc_conversion(8'h00, adc_resolution);
            end
            
            if (channel_counter == 24) begin
                cal_done <= 1'b1;
            end
        end
    end
    
    // ADC conversion simulation function
    function logic [11:0] perform_adc_conversion(input logic [7:0] analog_input, input logic [3:0] resolution);
        logic [11:0] digital_result;
        logic [3:0] noise;
        
        // Simulate ADC conversion with resolution scaling
        case (resolution)
            4'd8:  digital_result = {analog_input, 4'b0000};           // 8-bit mode
            4'd10: digital_result = {analog_input, 2'b00} + analog_input[7:6]; // 10-bit mode
            4'd12: digital_result = {analog_input, 4'b0000} + {analog_input[7:4], 4'b0000}; // 12-bit mode
            default: digital_result = {analog_input, 4'b0000};
        endcase
        
        // Add simulated noise (LFSR-based)
        noise = digital_result[3:0] ^ digital_result[7:4];
        digital_result = digital_result + noise;
        
        return digital_result;
    endfunction
    
    // ADC conversion for active channels
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int j = 0; j < 25; j++) begin
                adc_results[j] <= '0;
                done_flags[j] <= 1'b0;
            end
        end else begin
            case (state)
                CONVERT_CH_0_12: begin
                    if (conversion_timer >= CONVERSION_TIME && channel_counter <= 12) begin
                        adc_results[channel_counter] <= perform_adc_conversion(analog_currents[channel_counter], adc_resolution);
                        done_flags[channel_counter] <= 1'b1;
                    end
                end
                
                CONVERT_CH_13_24: begin
                    if (conversion_timer >= CONVERSION_TIME && channel_counter >= 13 && channel_counter <= 24) begin
                        adc_results[channel_counter] <= perform_adc_conversion(analog_currents[channel_counter], adc_resolution);
                        done_flags[channel_counter] <= 1'b1;
                    end
                end
                
                IDLE: begin
                    done_flags <= '0;
                end
            endcase
        end
    end
    
    // Apply calibration to results
    logic [11:0] calibrated_results [0:24];
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int k = 0; k < 25; k++) begin
                calibrated_results[k] <= '0;
            end
        end else if (state == APPLY_CALIBRATION) begin
            for (int m = 0; m < 25; m++) begin
                // Subtract calibration offset
                if (adc_results[m] >= cal_offsets[m]) begin
                    calibrated_results[m] <= adc_results[m] - cal_offsets[m];
                end else begin
                    calibrated_results[m] <= '0;
                end
            end
        end
    end
    
    // ADC clock generation (slower than system clock)
    logic [2:0] adc_clk_div;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            adc_clk_div <= '0;
        end else begin
            adc_clk_div <= adc_clk_div + 1;
        end
    end
    
    assign adc_clk = adc_clk_div[2]; // Divide by 8 for ADC timing
    
    // Channel enable and selection logic
    logic [24:0] enable_mask;
    always_comb begin
        enable_mask = '0;
        case (state)
            CONVERT_CH_0_12: enable_mask[12:0] = 13'h1FFF;
            CONVERT_CH_13_24: enable_mask[24:13] = 12'hFFF;
            SAMPLE_INPUTS: enable_mask = 25'h1FFFFFF;
            default: enable_mask = '0;
        endcase
    end
    
    assign adc_enable_mask = enable_mask;
    assign adc_channel_select = channel_counter;
    assign sample_hold = (state == SAMPLE_INPUTS);
    
    // Output validation and error detection
    logic [24:0] valid_results;
    logic conversion_err;
    
    always_comb begin
        valid_results = '0;
        conversion_err = 1'b0;
        
        for (int n = 0; n < 25; n++) begin
            // Check for reasonable ADC values
            if (calibrated_results[n] <= 12'hFFF && calibrated_results[n] >= 12'h000) begin
                valid_results[n] = 1'b1;
            end
            
            // Check for conversion errors (saturation, underflow)
            if (calibrated_results[n] == 12'hFFF || calibrated_results[n] == 12'h000) begin
                if (analog_currents[n] != 8'hFF && analog_currents[n] != 8'h00) begin
                    conversion_err = 1'b1;
                end
            end
        end
    end
    
    assign conversion_error = conversion_err;
    
    // Output assignments
    always_comb begin
        for (int p = 0; p < 25; p++) begin
            digital_outputs[p] = calibrated_results[p];
            calibration_offset[p] = cal_offsets[p];
        end
    end
    
    assign conversion_done = done_flags;
    assign all_conversions_done = &done_flags;
    assign data_valid = (state == COMPLETE) && !conversion_error;
    assign calibration_complete = cal_done;
    
    // Performance monitoring
    logic [15:0] total_conversion_time;
    logic [7:0] max_conversion_time;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            total_conversion_time <= '0;
            max_conversion_time <= '0;
        end else if (state == IDLE) begin
            total_conversion_time <= '0;
        end else if (state != IDLE && state != COMPLETE) begin
            total_conversion_time <= total_conversion_time + 1;
            if (conversion_timer > max_conversion_time) begin
                max_conversion_time <= conversion_timer;
            end
        end
    end
    
    // Debug outputs
    logic [3:0] debug_state;
    logic [4:0] debug_channel;
    logic [15:0] debug_time;
    
    assign debug_state = state;
    assign debug_channel = channel_counter;
    assign debug_time = total_conversion_time;
    
endmodule
