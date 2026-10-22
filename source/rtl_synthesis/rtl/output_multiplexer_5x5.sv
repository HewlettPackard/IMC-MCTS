// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// Output Multiplexer for 5x5 Go Board Selection Unit
// Routes the selected child's information to output based on best_child_index
// Handles 4 children per node with their corresponding data

module output_multiplexer_5x5 (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [1:0]  best_child_index,   // Selected child index (0-3)
    
    // Child 0 inputs
    input  logic [6:0]  child0_address,     // Node address for child 0
    input  logic [24:0] child0_board_state, // 5x5 board state
    input  logic        child0_player,      // Current player
    input  logic [15:0] child0_wins,        // Win count
    input  logic [15:0] child0_visits,      // Visit count
    input  logic [31:0] child0_ucb1,        // UCB1 value
    
    // Child 1 inputs  
    input  logic [6:0]  child1_address,
    input  logic [24:0] child1_board_state,
    input  logic        child1_player,
    input  logic [15:0] child1_wins,
    input  logic [15:0] child1_visits,
    input  logic [31:0] child1_ucb1,
    
    // Child 2 inputs
    input  logic [6:0]  child2_address,
    input  logic [24:0] child2_board_state,
    input  logic        child2_player,
    input  logic [15:0] child2_wins,
    input  logic [15:0] child2_visits,
    input  logic [31:0] child2_ucb1,
    
    // Child 3 inputs
    input  logic [6:0]  child3_address,
    input  logic [24:0] child3_board_state,
    input  logic        child3_player,
    input  logic [15:0] child3_wins,
    input  logic [15:0] child3_visits,
    input  logic [31:0] child3_ucb1,
    
    // Selected child outputs
    output logic [6:0]  selected_address,
    output logic [24:0] selected_board_state,
    output logic        selected_player,
    output logic [15:0] selected_wins,
    output logic [15:0] selected_visits,
    output logic [31:0] selected_ucb1,
    output logic [1:0]  selected_index,
    output logic        output_valid
);

    // Internal registers for output stability
    logic [6:0]  addr_reg;
    logic [24:0] board_reg;
    logic        player_reg;
    logic [15:0] wins_reg;
    logic [15:0] visits_reg;
    logic [31:0] ucb1_reg;
    logic [1:0]  index_reg;
    logic        valid_reg;
    
    // Multiplexer logic with registered outputs
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            addr_reg <= '0;
            board_reg <= '0;
            player_reg <= 1'b0;
            wins_reg <= '0;
            visits_reg <= '0;
            ucb1_reg <= '0;
            index_reg <= '0;
            valid_reg <= 1'b0;
        end else if (enable) begin
            valid_reg <= 1'b1;
            index_reg <= best_child_index;
            
            case (best_child_index)
                2'b00: begin // Child 0 selected
                    addr_reg <= child0_address;
                    board_reg <= child0_board_state;
                    player_reg <= child0_player;
                    wins_reg <= child0_wins;
                    visits_reg <= child0_visits;
                    ucb1_reg <= child0_ucb1;
                end
                
                2'b01: begin // Child 1 selected
                    addr_reg <= child1_address;
                    board_reg <= child1_board_state;
                    player_reg <= child1_player;
                    wins_reg <= child1_wins;
                    visits_reg <= child1_visits;
                    ucb1_reg <= child1_ucb1;
                end
                
                2'b10: begin // Child 2 selected
                    addr_reg <= child2_address;
                    board_reg <= child2_board_state;
                    player_reg <= child2_player;
                    wins_reg <= child2_wins;
                    visits_reg <= child2_visits;
                    ucb1_reg <= child2_ucb1;
                end
                
                2'b11: begin // Child 3 selected
                    addr_reg <= child3_address;
                    board_reg <= child3_board_state;
                    player_reg <= child3_player;
                    wins_reg <= child3_wins;
                    visits_reg <= child3_visits;
                    ucb1_reg <= child3_ucb1;
                end
                
                default: begin
                    addr_reg <= '0;
                    board_reg <= '0;
                    player_reg <= 1'b0;
                    wins_reg <= '0;
                    visits_reg <= '0;
                    ucb1_reg <= '0;
                end
            endcase
        end else begin
            valid_reg <= 1'b0;
        end
    end
    
    // Combinatorial multiplexer for immediate output (optional fast path)
    logic [6:0]  addr_comb;
    logic [24:0] board_comb;
    logic        player_comb;
    logic [15:0] wins_comb;
    logic [15:0] visits_comb;
    logic [31:0] ucb1_comb;
    
    always_comb begin
        case (best_child_index)
            2'b00: begin
                addr_comb = child0_address;
                board_comb = child0_board_state;
                player_comb = child0_player;
                wins_comb = child0_wins;
                visits_comb = child0_visits;
                ucb1_comb = child0_ucb1;
            end
            
            2'b01: begin
                addr_comb = child1_address;
                board_comb = child1_board_state;
                player_comb = child1_player;
                wins_comb = child1_wins;
                visits_comb = child1_visits;
                ucb1_comb = child1_ucb1;
            end
            
            2'b10: begin
                addr_comb = child2_address;
                board_comb = child2_board_state;
                player_comb = child2_player;
                wins_comb = child2_wins;
                visits_comb = child2_visits;
                ucb1_comb = child2_ucb1;
            end
            
            2'b11: begin
                addr_comb = child3_address;
                board_comb = child3_board_state;
                player_comb = child3_player;
                wins_comb = child3_wins;
                visits_comb = child3_visits;
                ucb1_comb = child3_ucb1;
            end
            
            default: begin
                addr_comb = '0;
                board_comb = '0;
                player_comb = 1'b0;
                wins_comb = '0;
                visits_comb = '0;
                ucb1_comb = '0;
            end
        endcase
    end
    
    // Output assignments (using registered values for stability)
    assign selected_address = addr_reg;
    assign selected_board_state = board_reg;
    assign selected_player = player_reg;
    assign selected_wins = wins_reg;
    assign selected_visits = visits_reg;
    assign selected_ucb1 = ucb1_reg;
    assign selected_index = index_reg;
    assign output_valid = valid_reg;
    
    // Additional validation logic
    logic inputs_valid;
    assign inputs_valid = (child0_address != '0) || (child1_address != '0) || 
                         (child2_address != '0) || (child3_address != '0);
    
    // Error detection for invalid selections
    logic selection_error;
    assign selection_error = enable && !inputs_valid;
    
    // Debug outputs (can be used for verification)
    logic [3:0] child_valid_mask;
    assign child_valid_mask[0] = (child0_address != '0);
    assign child_valid_mask[1] = (child1_address != '0);
    assign child_valid_mask[2] = (child2_address != '0);
    assign child_valid_mask[3] = (child3_address != '0);
    
endmodule
