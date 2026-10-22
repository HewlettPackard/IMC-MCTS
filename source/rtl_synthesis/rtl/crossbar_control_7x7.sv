// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Crossbar Control for 7x7 Go Board
// Controls 49x49 memristor crossbar array for neural network rollout computation
// Manages voltage application and current sensing for game state evaluation

module crossbar_control_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [7:0]  input_voltages [0:48],   // Input voltages from DACs (49 inputs)
    input  logic        computation_start,
    input  logic [3:0]  pulse_width,             // Control pulse width
    input  logic [3:0]  pulse_amplitude,         // Control pulse amplitude
    output logic [48:0] row_enables,             // Row enable signals (49 rows)
    output logic [48:0] col_enables,             // Column enable signals (49 columns)
    output logic [7:0]  row_voltages [0:48],     // Voltage applied to each row
    output logic [7:0]  col_voltages [0:48],     // Voltage applied to each column
    output logic        crossbar_active,
    output logic        computation_complete,
    
    // Crossbar timing and control
    output logic        row_clk,
    output logic        col_clk,
    output logic [5:0]  current_row,             // Currently active row (0-48)
    output logic [5:0]  current_col,             // Currently active column (0-48)
    output logic        pulse_enable
);

    // Internal registers
    logic [3:0]  state, next_state;
    logic [5:0]  row_counter;
    logic [5:0]  col_counter;
    logic [7:0]  pulse_counter;
    logic [48:0] active_rows;
    logic [48:0] active_cols;
    logic [7:0]  voltage_buffer [0:48];
    logic        computation_active;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam SETUP_VOLTAGES = 4'b0001;
    localparam ENABLE_ROWS = 4'b0010;
    localparam ENABLE_COLS = 4'b0011;
    localparam APPLY_PULSE = 4'b0100;
    localparam SCAN_MATRIX = 4'b0101;
    localparam NEXT_ROW = 4'b0110;
    localparam NEXT_COL = 4'b0111;
    localparam SETTLE_TIME = 4'b1000;
    localparam COMPLETE = 4'b1001;
    
    // Crossbar scanning parameters
    localparam PULSE_DURATION = 8'd16;          // Pulse duration in clock cycles
    localparam SETTLE_CYCLES = 8'd8;            // Settlement time between operations
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            row_counter <= '0;
            col_counter <= '0;
            pulse_counter <= '0;
            active_rows <= '0;
            active_cols <= '0;
            computation_active <= 1'b0;
            // Initialize voltage buffer
            for (int i = 0; i < 49; i++) begin
                voltage_buffer[i] <= '0;
            end
        end else begin
            state <= next_state;
            
            case (state)
                SETUP_VOLTAGES: begin
                    // Copy input voltages to internal buffer
                    for (int j = 0; j < 49; j++) begin
                        voltage_buffer[j] <= input_voltages[j];
                    end
                    row_counter <= '0;
                    col_counter <= '0;
                    computation_active <= 1'b1;
                end
                
                ENABLE_ROWS: begin
                    // Enable current row
                    active_rows <= '0;
                    if (row_counter < 49) begin
                        active_rows[row_counter] <= 1'b1;
                    end
                end
                
                ENABLE_COLS: begin
                    // Enable all columns for current computation
                    active_cols <= {49{1'b1}};
                    pulse_counter <= '0;
                end
                
                APPLY_PULSE: begin
                    if (pulse_counter < PULSE_DURATION) begin
                        pulse_counter <= pulse_counter + 1;
                    end
                end
                
                SCAN_MATRIX: begin
                    // Matrix scanning complete for current row
                    pulse_counter <= '0;
                end
                
                NEXT_ROW: begin
                    if (row_counter < 48) begin
                        row_counter <= row_counter + 1;
                    end
                end
                
                SETTLE_TIME: begin
                    if (pulse_counter < SETTLE_CYCLES) begin
                        pulse_counter <= pulse_counter + 1;
                    end
                end
                
                IDLE: begin
                    row_counter <= '0;
                    col_counter <= '0;
                    pulse_counter <= '0;
                    active_rows <= '0;
                    active_cols <= '0;
                    computation_active <= 1'b0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        
        case (state)
            IDLE: begin
                if (enable && computation_start)
                    next_state = SETUP_VOLTAGES;
            end
            
            SETUP_VOLTAGES:
                next_state = ENABLE_ROWS;
                
            ENABLE_ROWS:
                next_state = ENABLE_COLS;
                
            ENABLE_COLS:
                next_state = APPLY_PULSE;
                
            APPLY_PULSE: begin
                if (pulse_counter >= PULSE_DURATION)
                    next_state = SCAN_MATRIX;
            end
            
            SCAN_MATRIX: begin
                if (row_counter >= 48)
                    next_state = SETTLE_TIME;
                else
                    next_state = NEXT_ROW;
            end
            
            NEXT_ROW:
                next_state = ENABLE_ROWS;
                
            SETTLE_TIME: begin
                if (pulse_counter >= SETTLE_CYCLES)
                    next_state = COMPLETE;
            end
            
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // Voltage application logic
    always_comb begin
        // Default assignments
        for (int k = 0; k < 49; k++) begin
            row_voltages[k] = 8'h00;
            col_voltages[k] = 8'h00;
        end
        
        // Apply voltages during active states
        if (state == APPLY_PULSE && computation_active) begin
            // Apply row voltage
            if (row_counter < 49) begin
                row_voltages[row_counter] = (voltage_buffer[row_counter] * pulse_amplitude) >> 4;
            end
            
            // Apply column voltages
            for (int m = 0; m < 49; m++) begin
                if (active_cols[m]) begin
                    col_voltages[m] = voltage_buffer[m] >> 1; // Reduced amplitude for columns
                end
            end
        end
    end
    
    // Pulse generation
    logic pulse_active;
    always_comb begin
        pulse_active = (state == APPLY_PULSE) && 
                      (pulse_counter < pulse_width) && 
                      computation_active;
    end
    
    // Clock generation for row/column sequencing
    logic [3:0] clk_divider;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            clk_divider <= '0;
        end else begin
            clk_divider <= clk_divider + 1;
        end
    end
    
    // Output assignments
    assign row_enables = active_rows;
    assign col_enables = active_cols;
    assign crossbar_active = computation_active;
    assign computation_complete = (state == COMPLETE);
    assign row_clk = clk_divider[1]; // Divided clock for row operations
    assign col_clk = clk_divider[0]; // Divided clock for column operations
    assign current_row = row_counter;
    assign current_col = col_counter;
    assign pulse_enable = pulse_active;

endmodule
