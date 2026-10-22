// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Path Address Extractor for 5x5 Go Board
// Extracts node addresses from the MCTS path for backpropagation updates
// Handles variable-length paths with proper addressing for 25-position board

module path_address_extractor_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [6:0]  path_addresses [0:31],   // MCTS path (max 32 nodes deep)
    input  logic [4:0]  path_length,             // Actual path length
    input  logic        extraction_start,
    output logic [6:0]  extracted_addresses [0:31], // Extracted addresses
    output logic [4:0]  extracted_count,         // Number of valid addresses
    output logic        extraction_complete,
    output logic        addresses_valid,
    
    // Address validation and filtering
    output logic [31:0] valid_address_mask,      // Mask indicating valid addresses
    output logic [4:0]  invalid_addresses,      // Count of invalid addresses found
    output logic        path_integrity_ok
);

    // Internal registers
    logic [3:0]  state, next_state;
    logic [4:0]  address_counter;
    logic [6:0]  temp_addresses [0:31];
    logic [4:0]  valid_count;
    logic [31:0] validity_mask;
    logic [4:0]  invalid_count;
    
    // State encoding
    localparam IDLE = 4'b0000;
    localparam VALIDATE_INPUT = 4'b0001;
    localparam EXTRACT_ADDRESSES = 4'b0010;
    localparam VALIDATE_ADDRESSES = 4'b0011;
    localparam REMOVE_DUPLICATES = 4'b0100;
    localparam SORT_ADDRESSES = 4'b0101;
    localparam COMPLETE = 4'b0110;
    
    // Maximum valid address for 5x5 board (25 positions * 4 children = 100 max addresses)
    localparam [6:0] MAX_VALID_ADDRESS = 7'd99;
    
    // State machine
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state <= IDLE;
            address_counter <= '0;
        end else begin
            state <= next_state;
            
            case (state)
                EXTRACT_ADDRESSES, VALIDATE_ADDRESSES, REMOVE_DUPLICATES: begin
                    if (address_counter < path_length - 1) begin
                        address_counter <= address_counter + 1;
                    end
                end
                
                IDLE: begin
                    address_counter <= '0;
                end
            endcase
        end
    end
    
    // Next state logic
    always_comb begin
        next_state = state;
        case (state)
            IDLE: if (enable && extraction_start) next_state = VALIDATE_INPUT;
            VALIDATE_INPUT: next_state = EXTRACT_ADDRESSES;
            EXTRACT_ADDRESSES: if (address_counter >= path_length - 1) next_state = VALIDATE_ADDRESSES;
            VALIDATE_ADDRESSES: if (address_counter >= path_length - 1) next_state = REMOVE_DUPLICATES;
            REMOVE_DUPLICATES: if (address_counter >= path_length - 1) next_state = SORT_ADDRESSES;
            SORT_ADDRESSES: next_state = COMPLETE;
            COMPLETE: next_state = IDLE;
            default: next_state = IDLE;
        endcase
    end
    
    // Input validation
    logic input_valid;
    always_comb begin
        input_valid = 1'b1;
        
        // Check path length validity
        if (path_length == 0 || path_length > 32) begin
            input_valid = 1'b0;
        end
        
        // Check for null addresses at start of path
        if (path_addresses[0] == 7'b0) begin
            input_valid = 1'b0;
        end
    end
    
    // Address extraction process
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int i = 0; i < 32; i++) begin
                temp_addresses[i] <= '0;
            end
            valid_count <= '0;
        end else if (state == EXTRACT_ADDRESSES) begin
            if (address_counter < path_length) begin
                temp_addresses[address_counter] <= path_addresses[address_counter];
                if (path_addresses[address_counter] != 7'b0) begin
                    valid_count <= valid_count + 1;
                end
            end
        end else if (state == IDLE) begin
            valid_count <= '0;
        end
    end
    
    // Address validation process
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            validity_mask <= '0;
            invalid_count <= '0;
        end else if (state == VALIDATE_ADDRESSES) begin
            if (address_counter == 0) begin
                validity_mask <= '0;
                invalid_count <= '0;
            end
            
            if (address_counter < path_length) begin
                logic [6:0] current_addr = temp_addresses[address_counter];
                
                // Check if address is within valid range for 5x5 board
                if (current_addr <= MAX_VALID_ADDRESS && current_addr != 7'b0) begin
                    validity_mask[address_counter] <= 1'b1;
                end else begin
                    validity_mask[address_counter] <= 1'b0;
                    invalid_count <= invalid_count + 1;
                end
            end
        end
    end
    
    // Duplicate removal process
    logic [6:0] unique_addresses [0:31];
    logic [4:0] unique_count;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int j = 0; j < 32; j++) begin
                unique_addresses[j] <= '0;
            end
            unique_count <= '0;
        end else if (state == REMOVE_DUPLICATES) begin
            if (address_counter == 0) begin
                unique_count <= '0;
                for (int k = 0; k < 32; k++) begin
                    unique_addresses[k] <= '0;
                end
            end
            
            if (address_counter < path_length && validity_mask[address_counter]) begin
                logic [6:0] current_addr = temp_addresses[address_counter];
                logic is_duplicate = 1'b0;
                
                // Check if address already exists in unique list
                for (int m = 0; m < unique_count; m++) begin
                    if (unique_addresses[m] == current_addr) begin
                        is_duplicate = 1'b1;
                    end
                end
                
                // Add to unique list if not duplicate
                if (!is_duplicate && unique_count < 32) begin
                    unique_addresses[unique_count] <= current_addr;
                    unique_count <= unique_count + 1;
                end
            end
        end
    end
    
    // Sorting process (bubble sort for small arrays)
    logic [6:0] sorted_addresses [0:31];
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            for (int n = 0; n < 32; n++) begin
                sorted_addresses[n] <= '0;
            end
        end else if (state == SORT_ADDRESSES) begin
            // Copy unique addresses to sorted array
            for (int p = 0; p < 32; p++) begin
                sorted_addresses[p] <= unique_addresses[p];
            end
            
            // Simple bubble sort for demonstration (synthesis tools may optimize)
            for (int q = 0; q < unique_count - 1; q++) begin
                for (int r = 0; r < unique_count - 1 - q; r++) begin
                    if (sorted_addresses[r] > sorted_addresses[r + 1] && sorted_addresses[r + 1] != 7'b0) begin
                        logic [6:0] temp = sorted_addresses[r];
                        sorted_addresses[r] <= sorted_addresses[r + 1];
                        sorted_addresses[r + 1] <= temp;
                    end
                end
            end
        end
    end
    
    // Path integrity checking
    logic path_integrity;
    always_comb begin
        path_integrity = 1'b1;
        
        // Check for gaps in the path
        for (int s = 1; s < path_length; s++) begin
            if (path_addresses[s-1] != 7'b0 && path_addresses[s] == 7'b0) begin
                // Gap found in middle of path
                path_integrity = 1'b0;
            end
        end
        
        // Check for reasonable address progression
        for (int t = 1; t < path_length; t++) begin
            logic [6:0] addr_diff = (path_addresses[t] > path_addresses[t-1]) ? 
                                   (path_addresses[t] - path_addresses[t-1]) : 
                                   (path_addresses[t-1] - path_addresses[t]);
            
            // Addresses should not jump by more than max children (4) between levels
            if (addr_diff > 4 && path_addresses[t] != 7'b0 && path_addresses[t-1] != 7'b0) begin
                path_integrity = 1'b0;
            end
        end
    end
    
    // Output assignments
    always_comb begin
        for (int u = 0; u < 32; u++) begin
            extracted_addresses[u] = sorted_addresses[u];
        end
    end
    
    assign extracted_count = unique_count;
    assign extraction_complete = (state == COMPLETE);
    assign addresses_valid = (state == COMPLETE) && input_valid;
    assign valid_address_mask = validity_mask;
    assign invalid_addresses = invalid_count;
    assign path_integrity_ok = path_integrity && input_valid;
    
    // Advanced path analysis
    logic [4:0] path_depth;
    logic [6:0] root_address;
    logic [6:0] leaf_address;
    
    always_comb begin
        path_depth = 5'b0;
        root_address = 7'b0;
        leaf_address = 7'b0;
        
        // Calculate effective path depth
        for (int v = 0; v < 32; v++) begin
            if (path_addresses[v] != 7'b0) begin
                path_depth = path_depth + 1;
            end
        end
        
        // Identify root and leaf addresses
        if (path_length > 0) begin
            root_address = path_addresses[0];
            for (int w = 31; w >= 0; w--) begin
                if (path_addresses[w] != 7'b0) begin
                    leaf_address = path_addresses[w];
                    break;
                end
            end
        end
    end
    
    // Performance monitoring
    logic [7:0] extraction_cycles;
    logic [4:0] max_path_length;
    
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            extraction_cycles <= '0;
            max_path_length <= '0;
        end else if (state == IDLE) begin
            extraction_cycles <= '0;
        end else if (state != IDLE && state != COMPLETE) begin
            extraction_cycles <= extraction_cycles + 1;
        end
        
        if (path_length > max_path_length) begin
            max_path_length <= path_length;
        end
    end
    
    // Debug outputs
    logic [3:0] debug_state;
    logic [4:0] debug_counter;
    logic [4:0] debug_depth;
    
    assign debug_state = state;
    assign debug_counter = address_counter;
    assign debug_depth = path_depth;
    
endmodule
