// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Rollout Unit - Crossbar Control
// 2x2 Board Accelerator Architecture
// ============================================================================

module crossbar_control (
    input  logic       clk,
    input  logic       rst_n,
    input  logic       enable,
    input  logic       start_computation,
    input  logic       dac_ready,
    
    output logic [3:0] row_enable,
    output logic [3:0] col_enable,
    output logic       crossbar_active,
    output logic       computation_done
);

    typedef enum logic [1:0] {
        IDLE        = 2'b00,
        ACTIVE      = 2'b01,
        COMPUTE     = 2'b10,
        DONE        = 2'b11
    } state_t;

    state_t current_state, next_state;

    // State machine for crossbar control
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_state <= IDLE;
        end else begin
            current_state <= next_state;
        end
    end

    // Next state logic
    always_comb begin
        case (current_state)
            IDLE: begin
                if (enable && start_computation && dac_ready)
                    next_state = ACTIVE;
                else
                    next_state = IDLE;
            end
            ACTIVE: begin
                next_state = COMPUTE;
            end
            COMPUTE: begin
                next_state = DONE;
            end
            DONE: begin
                if (!enable)
                    next_state = IDLE;
                else
                    next_state = DONE;
            end
            default: next_state = IDLE;
        endcase
    end

    // Output logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            row_enable       <= 4'h0;
            col_enable       <= 4'h0;
            crossbar_active  <= 1'b0;
            computation_done <= 1'b0;
        end else begin
            case (current_state)
                IDLE: begin
                    row_enable       <= 4'h0;
                    col_enable       <= 4'h0;
                    crossbar_active  <= 1'b0;
                    computation_done <= 1'b0;
                end
                ACTIVE, COMPUTE: begin
                    row_enable       <= 4'hF; // Activate all rows
                    col_enable       <= 4'hF; // Activate all columns
                    crossbar_active  <= 1'b1;
                    computation_done <= 1'b0;
                end
                DONE: begin
                    row_enable       <= 4'h0;
                    col_enable       <= 4'h0;
                    crossbar_active  <= 1'b0;
                    computation_done <= 1'b1;
                end
            endcase
        end
    end

endmodule
