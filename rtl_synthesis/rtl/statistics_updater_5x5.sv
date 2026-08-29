// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Statistics Updater for 5x5 Go Board
// Updates win/visit statistics for nodes in the MCTS backpropagation path
// Handles concurrent updates with proper synchronization and overflow protection

module statistics_updater_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [6:0]  node_addresses [0:31],   // Addresses to update
    input  logic [4:0]  address_count,           // Number of valid addresses
    input  logic        game_result,             // 0=loss, 1=win for the player
    input  logic        player_perspective,      // Which player's perspective
    input  logic        update_start,
    output logic        update_complete,
    output logic        statistics_valid,
    
    // Memory interface for statistics SRAM (14KB for 5x5)
    output logic        stats_mem_en,
    output logic        stats_mem_we,
    output logic [13:0] stats_mem_addr,
    output logic [31:0] stats_mem_wdata,
    input  logic [31:0] stats_mem_rdata,
    
    // Update status and monitoring
    output logic [4:0]  updates_completed,
    output logic [4:0]  updates_failed,
    output logic        overflow_detected,
    output logic        memory_conflict
);

    // Internal registers
    logic [3:0]  state, next_state;
    logic [4:0]  address_index;
    logic [6:0]  current_address;
    logic [15:0] current_wins, current_visits;
    logic [15:0] new_wins, new_visits;
    logic [4:0]  completed_count, failed_count;
    logic        overflow_flag, conflict_flag;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam VALIDATE_INPUTS = 4'b0001;
    localparam READ_CURRENT_STATS = 4'b0010;
    localparam WAIT_READ_DATA = 4'b0011;
    localparam CALCULATE_UPDATES = 4'b0100;
    localparam WRITE_NEW_STATS = 4'b0101;
    localparam WAIT_WRITE_COMPLETE = 4'b0110;
    localparam NEXT_ADDRESS = 4'b0111;
    localparam COMPLETE = 4'b1000;
    
    // Memory timing parameters
    localparam [2:0] READ_LATENCY = 3'd2;   // Clock cycles for read
    localparam [2:0] WRITE_LATENCY = 3'd1;  // Clock cycles for write
    
    // Overflow protection limits
    localparam [15:0] MAX_WINS = 16'hFFFE;   // Maximum win count
    localparam [15:0] MAX_VISITS = 16'hFFFE; // Maximum visit count
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            address_index <= '0;
            current_address <= '0;
        end else begin
            state <= next_state;
            
            case (state)
                VALIDATE_INPUTS: begin
                    address_index <= '0;
                    current_address <= node_addresses[0];
                end
                
                NEXT_ADDRESS: begin
                    if (address_index < address_count - 1) begin
                        address_index <= address_index + 1;
                        current_address <= node_addresses[address_index + 1];
                    end
                end
                
                IDLE: begin
                    address_index <= '0;
                    current_address <= '0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        case (state)
            IDLE: if (enable && update_start) next_state = VALIDATE_INPUTS;
            VALIDATE_INPUTS: next_state = READ_CURRENT_STATS;
            READ_CURRENT_STATS: next_state = WAIT_READ_DATA;
            WAIT_READ_DATA: next_state = CALCULATE_UPDATES;
            CALCULATE_UPDATES: next_state = WRITE_NEW_STATS;
            WRITE_NEW_STATS: next_state = WAIT_WRITE_COMPLETE;
            WAIT_WRITE_COMPLETE: begin
                if (address_index >= address_count - 1) next_state = COMPLETE;
                else next_state = NEXT_ADDRESS;
            end
            NEXT_ADDRESS: next_state = READ_CURRENT_STATS;
            COMPLETE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end
    
    // Address validation
    logic address_valid;
    always_comb begin
        address_valid = 1'b1;
        
        // Check if current address is within valid range
        // For 5x5 board: 25 positions * 4 children = 100 max node addresses
        if (current_address > 7'd99) begin
            address_valid = 1'b0;
        end
        
        // Check for null address
        if (current_address == 7'b0) begin
            address_valid = 1'b0;
        end
    end
    
    // Memory address calculation
    logic [13:0] memory_address;
    always_comb begin
        // Each node stores 32-bit data (16-bit wins + 16-bit visits)
        // Address = node_address * 4 (bytes per entry)
        memory_address = {current_address, 2'b00}; // Multiply by 4
    end
    
    // Memory read operation
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            current_wins <= '0;
            current_visits <= '0;
        end else if (state == WAIT_READ_DATA) begin
            // Extract wins and visits from read data
            current_wins <= stats_mem_rdata[31:16];    // Upper 16 bits = wins
            current_visits <= stats_mem_rdata[15:0];   // Lower 16 bits = visits
        end
    end
    
    // Statistics calculation
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            new_wins <= '0;
            new_visits <= '0;
            overflow_flag <= 1'b0;
        end else if (state == CALCULATE_UPDATES) begin
            // Always increment visit count
            if (current_visits < MAX_VISITS) begin
                new_visits <= current_visits + 1;
            end else begin
                new_visits <= MAX_VISITS;
                overflow_flag <= 1'b1;
            end
            
            // Increment win count based on game result and player perspective
            logic should_increment_wins;
            should_increment_wins = (game_result == player_perspective);
            
            if (should_increment_wins && current_wins < MAX_WINS) begin
                new_wins <= current_wins + 1;
            end else if (should_increment_wins) begin
                new_wins <= MAX_WINS;
                overflow_flag <= 1'b1;
            end else begin
                new_wins <= current_wins; // No change to wins
            end
        end
    end
    
    // Memory write operations
    logic [31:0] write_data;
    always_comb begin
        write_data = {new_wins, new_visits}; // Pack wins and visits
    end
    
    // Memory interface control
    always_comb begin
        case (state)
            READ_CURRENT_STATS: begin
                stats_mem_en = 1'b1;
                stats_mem_we = 1'b0;
                stats_mem_addr = memory_address;
                stats_mem_wdata = '0;
            end
            
            WRITE_NEW_STATS: begin
                stats_mem_en = 1'b1;
                stats_mem_we = 1'b1;
                stats_mem_addr = memory_address;
                stats_mem_wdata = write_data;
            end
            
            default: begin
                stats_mem_en = 1'b0;
                stats_mem_we = 1'b0;
                stats_mem_addr = '0;
                stats_mem_wdata = '0;
            end
        endcase
    end
    
    // Update tracking
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            completed_count <= '0;
            failed_count <= '0;
        end else if (state == WAIT_WRITE_COMPLETE) begin
            if (address_valid && !overflow_flag) begin
                completed_count <= completed_count + 1;
            end else begin
                failed_count <= failed_count + 1;
            end
        end else if (state == IDLE) begin
            completed_count <= '0;
            failed_count <= '0;
        end
    end
    
    // Memory conflict detection
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            conflict_flag <= 1'b0;
        end else begin
            // Detect if multiple updates target the same address
            logic [6:0] check_addresses [0:31];
            for (int i = 0; i < 32; i++) begin
                check_addresses[i] = node_addresses[i];
            end
            
            conflict_flag <= 1'b0;
            for (int j = 0; j < address_count - 1; j++) begin
                for (int k = j + 1; k < address_count; k++) begin
                    if (check_addresses[j] == check_addresses[k] && check_addresses[j] != 7'b0) begin
                        conflict_flag <= 1'b1;
                    end
                end
            end
        end
    end
    
    // Win rate calculation for monitoring
    logic [7:0] current_win_rate;
    always_comb begin
        if (current_visits > 0) begin
            current_win_rate = (current_wins << 8) / current_visits; // Fixed-point percentage
        end else begin
            current_win_rate = 8'h80; // 50% default for unvisited nodes
        end
    end
    
    // Statistics validation
    logic stats_consistent;
    always_comb begin
        stats_consistent = 1'b1;
        
        // Wins should never exceed visits
        if (current_wins > current_visits) begin
            stats_consistent = 1'b0;
        end
        
        // Check for reasonable values
        if (current_visits == 0 && current_wins != 0) begin
            stats_consistent = 1'b0;
        end
    end
    
    // Output assignments
    assign update_complete = (state == COMPLETE);
    assign statistics_valid = (state == COMPLETE) && stats_consistent;
    assign updates_completed = completed_count;
    assign updates_failed = failed_count;
    assign overflow_detected = overflow_flag;
    assign memory_conflict = conflict_flag;
    
    // Performance monitoring
    logic [7:0] update_cycles;
    logic [15:0] total_updates_processed;
    logic [7:0] average_update_time;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            update_cycles <= '0;
            total_updates_processed <= '0;
            average_update_time <= '0;
        end else if (state == IDLE) begin
            update_cycles <= '0;
        end else if (state != IDLE && state != COMPLETE) begin
            update_cycles <= update_cycles + 1;
        end else if (state == COMPLETE) begin
            total_updates_processed <= total_updates_processed + address_count;
            if (total_updates_processed > 0) begin
                average_update_time <= update_cycles / address_count;
            end
        end
    end
    
    // Advanced statistics tracking
    logic [15:0] max_wins_observed;
    logic [15:0] max_visits_observed;
    logic [6:0]  most_visited_node;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            max_wins_observed <= '0;
            max_visits_observed <= '0;
            most_visited_node <= '0;
        end else if (state == WAIT_READ_DATA) begin
            if (current_wins > max_wins_observed) begin
                max_wins_observed <= current_wins;
            end
            if (current_visits > max_visits_observed) begin
                max_visits_observed <= current_visits;
                most_visited_node <= current_address;
            end
        end
    end
    
    // Debug outputs
    logic [3:0] debug_state;
    logic [6:0] debug_address;
    logic [15:0] debug_wins;
    logic [15:0] debug_visits;
    
    assign debug_state = state;
    assign debug_address = current_address;
    assign debug_wins = current_wins;
    assign debug_visits = current_visits;
    
endmodule
