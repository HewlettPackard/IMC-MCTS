// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Child Stats Access for 7x7 Go Board
// Retrieves visit counts and win statistics for child nodes
// Optimized for 49-child access patterns in 7x7 MCTS trees

module child_stats_access_7x7 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [15:0] child_addresses [0:48], // Addresses for up to 49 children
    input  logic [5:0]  num_children,       // Number of valid children (0-49)
    input  logic        fetch_all,          // Fetch all child statistics
    input  logic [5:0]  specific_child,     // Specific child index to fetch
    output logic [31:0] visit_counts [0:48], // Visit counts for each child
    output logic [31:0] win_counts [0:48],   // Win counts for each child
    output logic [15:0] win_rates [0:48],    // Calculated win rates (fixed-point)
    output logic        stats_valid,
    output logic        fetch_complete,
    output logic        data_ready
);

    // Internal registers
    logic [3:0]  state, next_state;
    logic [5:0]  fetch_counter;
    logic [31:0] visit_buffer [0:48];        // Buffer for 49 visit counts
    logic [31:0] win_buffer [0:48];          // Buffer for 49 win counts
    logic [15:0] rate_buffer [0:48];         // Buffer for 49 win rates
    logic [5:0]  current_child;
    logic [127:0] memory_data;               // Data from memory interface
    logic        memory_valid;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam SETUP_FETCH = 4'b0001;
    localparam REQUEST_MEMORY = 4'b0010;
    localparam WAIT_MEMORY = 4'b0011;
    localparam EXTRACT_STATS = 4'b0100;
    localparam CALCULATE_RATES = 4'b0101;
    localparam NEXT_CHILD = 4'b0110;
    localparam COMPLETE = 4'b0111;
    
    // Memory interface (connecting to node SRAM access)
    logic        mem_enable;
    logic [15:0] mem_address;
    logic        mem_read_enable;
    logic [127:0] mem_read_data;
    logic        mem_data_valid;
    logic        mem_ready;
    
    // Instantiate memory interface
    node_sram_access_7x7 memory_if (
        .clk(clk),
        .rst_n(rst_n),
        .enable(mem_enable),
        .node_address(mem_address),
        .read_enable(mem_read_enable),
        .write_enable(1'b0),
        .write_data(128'h0),
        .read_data(mem_read_data),
        .data_valid(mem_data_valid),
        .operation_complete(mem_ready),
        .memory_ready(),
        
        // SRAM interface (would connect to actual SRAM)
        .sram_clk(),
        .sram_ce_n(),
        .sram_we_n(),
        .sram_oe_n(),
        .sram_addr(),
        .sram_data(),
        .sram_be_n()
    );
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            fetch_counter <= '0;
            current_child <= '0;
            // Initialize buffers
            for (int i = 0; i < 49; i++) begin
                visit_buffer[i] <= '0;
                win_buffer[i] <= '0;
                rate_buffer[i] <= '0;
            end
        end else begin
            state <= next_state;
            
            case (state)
                SETUP_FETCH: begin
                    if (fetch_all) begin
                        fetch_counter <= '0;
                        current_child <= '0;
                    end else begin
                        current_child <= specific_child;
                        fetch_counter <= '0;
                    end
                end
                
                EXTRACT_STATS: begin
                    if (current_child < 49) begin
                        // Extract statistics from 128-bit memory data
                        // Format: [31:0] visit_count, [63:32] win_count, [95:64] other_stats
                        visit_buffer[current_child] <= mem_read_data[31:0];
                        win_buffer[current_child] <= mem_read_data[63:32];
                    end
                end
                
                CALCULATE_RATES: begin
                    if (current_child < 49 && visit_buffer[current_child] > 0) begin
                        // Calculate win rate as fixed-point (16-bit)
                        // Rate = (win_count * 65536) / visit_count
                        rate_buffer[current_child] <= 
                            (win_buffer[current_child] << 16) / visit_buffer[current_child];
                    end else begin
                        rate_buffer[current_child] <= 16'h0;
                    end
                end
                
                NEXT_CHILD: begin
                    if (fetch_all && fetch_counter < num_children - 1 && fetch_counter < 48) begin
                        fetch_counter <= fetch_counter + 1;
                        current_child <= fetch_counter + 1;
                    end
                end
                
                IDLE: begin
                    fetch_counter <= '0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        mem_enable = 1'b0;
        mem_read_enable = 1'b0;
        mem_address = 16'h0;
        
        case (state)
            IDLE: begin
                if (enable && num_children > 0)
                    next_state = SETUP_FETCH;
            end
            
            SETUP_FETCH:
                next_state = REQUEST_MEMORY;
                
            REQUEST_MEMORY: begin
                if (current_child < 49 && current_child < num_children) begin
                    mem_enable = 1'b1;
                    mem_read_enable = 1'b1;
                    mem_address = child_addresses[current_child];
                    next_state = WAIT_MEMORY;
                end else begin
                    next_state = COMPLETE;
                end
            end
            
            WAIT_MEMORY: begin
                if (mem_data_valid)
                    next_state = EXTRACT_STATS;
            end
            
            EXTRACT_STATS:
                next_state = CALCULATE_RATES;
                
            CALCULATE_RATES: begin
                if (fetch_all && fetch_counter < num_children - 1 && fetch_counter < 48)
                    next_state = NEXT_CHILD;
                else
                    next_state = COMPLETE;
            end
            
            NEXT_CHILD:
                next_state = REQUEST_MEMORY;
                
            COMPLETE:
                next_state = IDLE;
                
            default:
                next_state = IDLE;
        endcase
    end
    
    // Output assignments
    genvar i;
    generate
        for (i = 0; i < 49; i++) begin : stats_assign
            assign visit_counts[i] = visit_buffer[i];
            assign win_counts[i] = win_buffer[i];
            assign win_rates[i] = rate_buffer[i];
        end
    endgenerate
    
    assign stats_valid = (state == COMPLETE);
    assign fetch_complete = (state == COMPLETE);
    assign data_ready = (state == COMPLETE);

endmodule
