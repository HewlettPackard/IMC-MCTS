// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Crossbar Control for 5x5 Go Board Memristor Array
// Controls the memristor crossbar switches for neural network computation
// Manages row/column selection and timing for rollout evaluation

module crossbar_control_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic        computation_start,
    input  logic [7:0]  input_voltages [0:24],   // Voltages from DACs
    input  logic [1:0]  operation_mode,          // 00=eval, 01=train, 10=test, 11=reset
    output logic [24:0] row_enables,             // Row selection signals
    output logic [24:0] col_enables,             // Column selection signals
    output logic        crossbar_clk,            // Crossbar timing clock
    output logic        computation_active,
    output logic        computation_complete,
    
    // Memristor array interface
    output logic [7:0]  row_voltages [0:24],     // Voltage outputs to rows
    output logic [7:0]  col_voltages [0:24],     // Voltage outputs to columns
    output logic        array_enable,
    output logic        read_enable,
    output logic        write_enable,
    
    // Configuration and control
    input  logic [7:0]  timing_config,           // Timing configuration
    input  logic [3:0]  voltage_bias,            // Bias voltage setting
    output logic        timing_violation,
    output logic        array_fault
);

    // Internal registers
    logic [3:0]  state, next_state;
    logic [4:0]  row_counter, col_counter;
    logic [7:0]  timing_counter;
    logic [24:0] active_rows, active_cols;
    logic [7:0]  row_voltage_reg [0:24];
    logic [7:0]  col_voltage_reg [0:24];
    logic        array_en_reg;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam CONFIGURE = 4'b0001;
    localparam SETUP_ROWS = 4'b0010;
    localparam SETUP_COLS = 4'b0011;
    localparam APPLY_VOLTAGES = 4'b0100;
    localparam COMPUTATION = 4'b0101;
    localparam READ_RESULTS = 4'b0110;
    localparam RESET_ARRAY = 4'b0111;
    localparam COMPLETE = 4'b1000;
    
    // Timing parameters for 5x5 crossbar
    localparam [7:0] SETUP_TIME = 8'd10;     // Clock cycles for setup
    localparam [7:0] HOLD_TIME = 8'd5;       // Clock cycles for hold
    localparam [7:0] COMPUTE_TIME = 8'd50;   // Clock cycles for computation
    localparam [7:0] READ_TIME = 8'd20;      // Clock cycles for reading
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            row_counter <= '0;
            col_counter <= '0;
            timing_counter <= '0;
        end else begin
            state <= next_state;
            
            case (state)
                SETUP_ROWS: begin
                    if (row_counter < 24) begin
                        row_counter <= row_counter + 1;
                    end
                end
                
                SETUP_COLS: begin
                    if (col_counter < 24) begin
                        col_counter <= col_counter + 1;
                    end
                end
                
                APPLY_VOLTAGES, COMPUTATION, READ_RESULTS: begin
                    timing_counter <= timing_counter + 1;
                end
                
                IDLE, COMPLETE: begin
                    row_counter <= '0;
                    col_counter <= '0;
                    timing_counter <= '0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        case (state)
            IDLE: if (enable && computation_start) next_state = CONFIGURE;
            CONFIGURE: next_state = SETUP_ROWS;
            SETUP_ROWS: if (row_counter == 24) next_state = SETUP_COLS;
            SETUP_COLS: if (col_counter == 24) next_state = APPLY_VOLTAGES;
            APPLY_VOLTAGES: if (timing_counter >= SETUP_TIME) next_state = COMPUTATION;
            COMPUTATION: if (timing_counter >= COMPUTE_TIME) next_state = READ_RESULTS;
            READ_RESULTS: if (timing_counter >= READ_TIME) begin
                if (operation_mode == 2'b11) next_state = RESET_ARRAY;
                else next_state = COMPLETE;
            end
            RESET_ARRAY: next_state = COMPLETE;
            COMPLETE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end
    
    // Row and column enable logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            active_rows <= '0;
            active_cols <= '0;
        end else begin
            case (state)
                SETUP_ROWS: begin
                    // Enable rows sequentially based on operation mode
                    case (operation_mode)
                        2'b00: active_rows <= 25'h1FFFFFF; // All rows for evaluation
                        2'b01: active_rows[row_counter] <= 1'b1; // Selective for training
                        2'b10: active_rows <= 25'h0000001; // Single row for testing
                        2'b11: active_rows <= '0; // No rows for reset
                    endcase
                end
                
                SETUP_COLS: begin
                    // Enable columns based on operation mode
                    case (operation_mode)
                        2'b00: active_cols <= 25'h1FFFFFF; // All columns for evaluation
                        2'b01: active_cols[col_counter] <= 1'b1; // Selective for training
                        2'b10: active_cols <= 25'h0000001; // Single column for testing
                        2'b11: active_cols <= '0; // No columns for reset
                    endcase
                end
                
                IDLE, RESET_ARRAY: begin
                    active_rows <= '0;
                    active_cols <= '0;
                end
            endcase
        end
    end
    
    // Voltage application to rows and columns
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < 25; i++) begin
                row_voltage_reg[i] <= '0;
                col_voltage_reg[i] <= '0;
            end
            array_en_reg <= 1'b0;
        end else begin
            case (state)
                APPLY_VOLTAGES: begin
                    array_en_reg <= 1'b1;
                    for (int j = 0; j < 25; j++) begin
                        if (active_rows[j]) begin
                            row_voltage_reg[j] <= apply_bias(input_voltages[j], voltage_bias);
                        end else begin
                            row_voltage_reg[j] <= '0;
                        end
                        
                        if (active_cols[j]) begin
                            col_voltage_reg[j] <= apply_bias(input_voltages[j], voltage_bias);
                        end else begin
                            col_voltage_reg[j] <= '0;
                        end
                    end
                end
                
                COMPUTATION: begin
                    array_en_reg <= 1'b1;
                    // Maintain voltages during computation
                end
                
                RESET_ARRAY: begin
                    array_en_reg <= 1'b1;
                    // Apply reset voltages
                    for (int k = 0; k < 25; k++) begin
                        row_voltage_reg[k] <= 8'h80; // Mid-level reset voltage
                        col_voltage_reg[k] <= 8'h80;
                    end
                end
                
                IDLE, COMPLETE: begin
                    array_en_reg <= 1'b0;
                    for (int m = 0; m < 25; m++) begin
                        row_voltage_reg[m] <= '0;
                        col_voltage_reg[m] <= '0;
                    end
                end
            endcase
        end
    end
    
    // Bias voltage application function
    function logic [7:0] apply_bias(input logic [7:0] input_voltage, input logic [3:0] bias);
        logic [11:0] biased_result;
        biased_result = input_voltage + (bias << 2); // Scale bias by 4
        return (biased_result > 255) ? 8'hFF : biased_result[7:0];
    endfunction
    
    // Crossbar clock generation (phase-shifted from main clock)
    logic [1:0] clk_phase;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            clk_phase <= '0;
        end else begin
            clk_phase <= clk_phase + 1;
        end
    end
    
    assign crossbar_clk = clk_phase[1]; // Divide by 4
    
    // Timing violation detection
    logic setup_violation, hold_violation;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            setup_violation <= 1'b0;
            hold_violation <= 1'b0;
        end else begin
            // Check for setup time violations
            if (state == APPLY_VOLTAGES && timing_counter < SETUP_TIME && next_state != APPLY_VOLTAGES) begin
                setup_violation <= 1'b1;
            end
            
            // Check for hold time violations
            if (state == COMPUTATION && timing_counter < HOLD_TIME) begin
                hold_violation <= 1'b1;
            end
            
            if (state == IDLE) begin
                setup_violation <= 1'b0;
                hold_violation <= 1'b0;
            end
        end
    end
    
    assign timing_violation = setup_violation || hold_violation;
    
    // Array fault detection
    logic voltage_fault, enable_fault;
    always_comb begin
        voltage_fault = 1'b0;
        enable_fault = 1'b0;
        
        // Check for voltage faults
        for (int n = 0; n < 25; n++) begin
            if (row_voltage_reg[n] > 8'hF0 && active_rows[n]) begin
                voltage_fault = 1'b1;
            end
            if (col_voltage_reg[n] > 8'hF0 && active_cols[n]) begin
                voltage_fault = 1'b1;
            end
        end
        
        // Check for enable signal conflicts
        if ((active_rows & active_cols) != 0 && operation_mode != 2'b00) begin
            enable_fault = 1'b1;
        end
    end
    
    assign array_fault = voltage_fault || enable_fault;
    
    // Output assignments
    assign row_enables = active_rows;
    assign col_enables = active_cols;
    assign computation_active = (state != IDLE) && (state != COMPLETE);
    assign computation_complete = (state == COMPLETE);
    assign array_enable = array_en_reg;
    assign read_enable = (state == READ_RESULTS);
    assign write_enable = (state == APPLY_VOLTAGES) || (state == COMPUTATION);
    
    always_comb begin
        for (int p = 0; p < 25; p++) begin
            row_voltages[p] = row_voltage_reg[p];
            col_voltages[p] = col_voltage_reg[p];
        end
    end
    
    // Performance monitoring
    logic [15:0] total_computation_cycles;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            total_computation_cycles <= '0;
        end else if (state == IDLE) begin
            total_computation_cycles <= '0;
        end else if (computation_active) begin
            total_computation_cycles <= total_computation_cycles + 1;
        end
    end
    
endmodule
