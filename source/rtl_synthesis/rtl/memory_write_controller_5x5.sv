// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Memory Write Controller for 5x5 Go Board
// Controls memory write operations during MCTS backpropagation
// Handles write scheduling, arbitration, and error detection for statistics updates

module memory_write_controller_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic        write_request,
    input  logic [13:0] write_address,           // 14-bit address for 14KB SRAM
    input  logic [31:0] write_data,              // 32-bit data (wins + visits)
    input  logic [2:0]  write_priority,          // Priority level (0=low, 7=high)
    output logic        write_accepted,
    output logic        write_complete,
    output logic        write_error,
    
    // Memory interface
    output logic        mem_clk,
    output logic        mem_en,
    output logic        mem_we,
    output logic [13:0] mem_addr,
    output logic [31:0] mem_wdata,
    input  logic [31:0] mem_rdata,
    input  logic        mem_ready,
    
    // Write queue management
    input  logic        flush_queue,
    output logic [3:0]  queue_occupancy,
    output logic        queue_full,
    output logic        queue_empty,
    
    // Error detection and recovery
    output logic        address_error,
    output logic        data_corruption,
    output logic        timeout_error,
    input  logic        error_recovery_mode
);

    // Write queue structure
    typedef struct packed {
        logic [13:0] addr;
        logic [31:0] data;
        logic [2:0]  priority;
        logic        valid;
    } write_entry_t;
    
    // Internal registers
    logic [3:0]  state, next_state;
    write_entry_t write_queue [0:15];            // 16-entry write queue
    logic [3:0]  queue_head, queue_tail;
    logic [3:0]  queue_count;
    logic [7:0]  timeout_counter;
    logic [3:0]  current_entry_index;
    logic        write_in_progress;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam ACCEPT_REQUEST = 4'b0001;
    localparam QUEUE_WRITE = 4'b0010;
    localparam SELECT_NEXT = 4'b0011;
    localparam VALIDATE_WRITE = 4'b0100;
    localparam EXECUTE_WRITE = 4'b0101;
    localparam WAIT_COMPLETION = 4'b0110;
    localparam VERIFY_WRITE = 4'b0111;
    localparam ERROR_HANDLING = 4'b1000;
    localparam FLUSH_QUEUE_STATE = 4'b1001;
    
    // Timing parameters
    localparam [7:0] WRITE_TIMEOUT = 8'd50;      // Maximum cycles for write operation
    localparam [2:0] WRITE_LATENCY = 3'd3;       // Expected write completion time
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            timeout_counter <= '0;
            write_in_progress <= 1'b0;
        end else begin
            state <= next_state;
            
            case (state)
                EXECUTE_WRITE, WAIT_COMPLETION: begin
                    timeout_counter <= timeout_counter + 1;
                    write_in_progress <= 1'b1;
                end
                
                IDLE: begin
                    timeout_counter <= '0;
                    write_in_progress <= 1'b0;
                end
                
                default: begin
                    write_in_progress <= 1'b0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        case (state)
            IDLE: begin
                if (flush_queue) next_state = FLUSH_QUEUE_STATE;
                else if (write_request && !queue_full) next_state = ACCEPT_REQUEST;
                else if (!queue_empty) next_state = SELECT_NEXT;
            end
            ACCEPT_REQUEST: next_state = QUEUE_WRITE;
            QUEUE_WRITE: next_state = IDLE;
            SELECT_NEXT: next_state = VALIDATE_WRITE;
            VALIDATE_WRITE: next_state = EXECUTE_WRITE;
            EXECUTE_WRITE: next_state = WAIT_COMPLETION;
            WAIT_COMPLETION: begin
                if (mem_ready) next_state = VERIFY_WRITE;
                else if (timeout_counter >= WRITE_TIMEOUT) next_state = ERROR_HANDLING;
            end
            VERIFY_WRITE: next_state = IDLE;
            ERROR_HANDLING: next_state = IDLE;
            FLUSH_QUEUE_STATE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end
    
    // Queue management
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            queue_head <= '0;
            queue_tail <= '0;
            queue_count <= '0;
            for (int i = 0; i < 16; i++) begin
                write_queue[i] <= '0;
            end
        end else begin
            case (state)
                QUEUE_WRITE: begin
                    // Add new write request to queue
                    write_queue[queue_tail].addr <= write_address;
                    write_queue[queue_tail].data <= write_data;
                    write_queue[queue_tail].priority <= write_priority;
                    write_queue[queue_tail].valid <= 1'b1;
                    
                    if (queue_count < 15) begin
                        queue_tail <= queue_tail + 1;
                        queue_count <= queue_count + 1;
                    end
                end
                
                VERIFY_WRITE: begin
                    // Remove completed write from queue
                    write_queue[queue_head].valid <= 1'b0;
                    if (queue_count > 0) begin
                        queue_head <= queue_head + 1;
                        queue_count <= queue_count - 1;
                    end
                end
                
                FLUSH_QUEUE_STATE: begin
                    // Clear entire queue
                    queue_head <= '0;
                    queue_tail <= '0;
                    queue_count <= '0;
                    for (int j = 0; j < 16; j++) begin
                        write_queue[j].valid <= 1'b0;
                    end
                end
            endcase
        end
    end
    
    // Priority-based write selection
    logic [3:0] highest_priority_index;
    logic [2:0] highest_priority;
    
    always_comb begin
        highest_priority_index = queue_head;
        highest_priority = 3'b000;
        
        // Find entry with highest priority
        for (int k = 0; k < 16; k++) begin
            if (write_queue[k].valid && write_queue[k].priority > highest_priority) begin
                highest_priority = write_queue[k].priority;
                highest_priority_index = k[3:0];
            end
        end
    end
    
    // Current write operation
    logic [13:0] current_write_addr;
    logic [31:0] current_write_data;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_write_addr <= '0;
            current_write_data <= '0;
            current_entry_index <= '0;
        end else if (state == SELECT_NEXT) begin
            current_entry_index <= highest_priority_index;
            current_write_addr <= write_queue[highest_priority_index].addr;
            current_write_data <= write_queue[highest_priority_index].data;
        end
    end
    
    // Address validation
    logic addr_valid;
    always_comb begin
        addr_valid = 1'b1;
        
        // Check address bounds for 14KB SRAM (0x0000 to 0x37FF)
        if (current_write_addr > 14'h37FF) begin
            addr_valid = 1'b0;
        end
        
        // Check for word alignment (addresses should be multiple of 4)
        if (current_write_addr[1:0] != 2'b00) begin
            addr_valid = 1'b0;
        end
    end
    
    // Data validation
    logic data_valid;
    always_comb begin
        data_valid = 1'b1;
        
        // Check that wins don't exceed visits
        logic [15:0] wins = current_write_data[31:16];
        logic [15:0] visits = current_write_data[15:0];
        
        if (wins > visits) begin
            data_valid = 1'b0;
        end
        
        // Check for reasonable values (visits should be non-zero if wins exist)
        if (wins > 0 && visits == 0) begin
            data_valid = 1'b0;
        end
    end
    
    // Memory interface control
    always_comb begin
        case (state)
            EXECUTE_WRITE: begin
                mem_en = 1'b1;
                mem_we = 1'b1;
                mem_addr = current_write_addr;
                mem_wdata = current_write_data;
            end
            
            VERIFY_WRITE: begin
                mem_en = 1'b1;
                mem_we = 1'b0;  // Read back for verification
                mem_addr = current_write_addr;
                mem_wdata = '0;
            end
            
            default: begin
                mem_en = 1'b0;
                mem_we = 1'b0;
                mem_addr = '0;
                mem_wdata = '0;
            end
        endcase
    end
    
    // Memory clock generation (phase-aligned with system clock)
    logic clk_delayed;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            clk_delayed <= 1'b0;
        end else begin
            clk_delayed <= clk;
        end
    end
    
    assign mem_clk = clk_delayed;
    
    // Write verification
    logic verification_passed;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            verification_passed <= 1'b0;
        end else if (state == VERIFY_WRITE) begin
            verification_passed <= (mem_rdata == current_write_data);
        end
    end
    
    // Error detection
    logic addr_err, data_corr, timeout_err;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            addr_err <= 1'b0;
            data_corr <= 1'b0;
            timeout_err <= 1'b0;
        end else begin
            case (state)
                VALIDATE_WRITE: begin
                    addr_err <= !addr_valid;
                    data_corr <= !data_valid;
                end
                
                WAIT_COMPLETION: begin
                    if (timeout_counter >= WRITE_TIMEOUT) begin
                        timeout_err <= 1'b1;
                    end
                end
                
                VERIFY_WRITE: begin
                    if (!verification_passed) begin
                        data_corr <= 1'b1;
                    end
                end
                
                IDLE: begin
                    addr_err <= 1'b0;
                    data_corr <= 1'b0;
                    timeout_err <= 1'b0;
                end
            endcase
        end
    end
    
    // Output assignments
    assign write_accepted = (state == ACCEPT_REQUEST);
    assign write_complete = (state == VERIFY_WRITE) && verification_passed;
    assign write_error = addr_err || data_corr || timeout_err;
    assign queue_occupancy = queue_count;
    assign queue_full = (queue_count >= 15);
    assign queue_empty = (queue_count == 0);
    assign address_error = addr_err;
    assign data_corruption = data_corr;
    assign timeout_error = timeout_err;
    
    // Performance monitoring
    logic [15:0] total_writes_completed;
    logic [15:0] total_write_errors;
    logic [7:0]  average_queue_occupancy;
    logic [7:0]  max_queue_occupancy;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            total_writes_completed <= '0;
            total_write_errors <= '0;
            average_queue_occupancy <= '0;
            max_queue_occupancy <= '0;
        end else begin
            if (write_complete) begin
                total_writes_completed <= total_writes_completed + 1;
            end
            
            if (write_error) begin
                total_write_errors <= total_write_errors + 1;
            end
            
            if (queue_count > max_queue_occupancy) begin
                max_queue_occupancy <= queue_count;
            end
            
            // Calculate running average of queue occupancy
            if (total_writes_completed > 0) begin
                average_queue_occupancy <= (average_queue_occupancy + queue_count) >> 1;
            end
        end
    end
    
    // Error recovery support
    logic recovery_active;
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            recovery_active <= 1'b0;
        end else if (error_recovery_mode && write_error) begin
            recovery_active <= 1'b1;
        end else if (!error_recovery_mode) begin
            recovery_active <= 1'b0;
        end
    end
    
    // Debug outputs
    logic [3:0] debug_state;
    logic [3:0] debug_queue_count;
    logic [7:0] debug_timeout;
    logic       debug_recovery;
    
    assign debug_state = state;
    assign debug_queue_count = queue_count;
    assign debug_timeout = timeout_counter;
    assign debug_recovery = recovery_active;
    
endmodule
