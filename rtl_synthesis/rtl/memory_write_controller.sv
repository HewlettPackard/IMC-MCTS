// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Backpropagation Unit - Memory Write Controller
// 2x2 Board Accelerator Architecture
// ============================================================================

module memory_write_controller (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [3:0]  write_addr_0,
    input  logic [3:0]  write_addr_1,
    input  logic [3:0]  write_addr_2,
    input  logic [15:0] write_data_0,   // 8-bit wins + 8-bit visits
    input  logic [15:0] write_data_1,
    input  logic [15:0] write_data_2,
    input  logic [2:0]  write_enable,
    input  logic        memory_ready,
    
    output logic [3:0]  sram_addr,
    output logic [15:0] sram_wdata,
    output logic        sram_wen,
    output logic        write_active,
    output logic        all_writes_done
);

    typedef enum logic [1:0] {
        IDLE    = 2'b00,
        WRITE_0 = 2'b01,
        WRITE_1 = 2'b10,
        WRITE_2 = 2'b11
    } state_t;

    state_t current_state, next_state;

    // State machine for write sequencing
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
                if (enable && memory_ready && |write_enable)
                    next_state = WRITE_0;
                else
                    next_state = IDLE;
            end
            WRITE_0: begin
                if (write_enable[1])
                    next_state = WRITE_1;
                else if (write_enable[2])
                    next_state = WRITE_2;
                else
                    next_state = IDLE;
            end
            WRITE_1: begin
                if (write_enable[2])
                    next_state = WRITE_2;
                else
                    next_state = IDLE;
            end
            WRITE_2: begin
                next_state = IDLE;
            end
            default: next_state = IDLE;
        endcase
    end

    // Output logic
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            sram_addr       <= 4'h0;
            sram_wdata      <= 16'h0;
            sram_wen        <= 1'b0;
            write_active    <= 1'b0;
            all_writes_done <= 1'b0;
        end else begin
            case (current_state)
                IDLE: begin
                    sram_wen        <= 1'b0;
                    write_active    <= 1'b0;
                    all_writes_done <= 1'b0;
                end
                WRITE_0: begin
                    if (write_enable[0]) begin
                        sram_addr  <= write_addr_0;
                        sram_wdata <= write_data_0;
                        sram_wen   <= 1'b1;
                    end else begin
                        sram_wen <= 1'b0;
                    end
                    write_active <= 1'b1;
                end
                WRITE_1: begin
                    if (write_enable[1]) begin
                        sram_addr  <= write_addr_1;
                        sram_wdata <= write_data_1;
                        sram_wen   <= 1'b1;
                    end else begin
                        sram_wen <= 1'b0;
                    end
                    write_active <= 1'b1;
                end
                WRITE_2: begin
                    if (write_enable[2]) begin
                        sram_addr  <= write_addr_2;
                        sram_wdata <= write_data_2;
                        sram_wen   <= 1'b1;
                    end else begin
                        sram_wen <= 1'b0;
                    end
                    write_active    <= 1'b1;
                    all_writes_done <= 1'b1;
                end
            endcase
        end
    end

endmodule
