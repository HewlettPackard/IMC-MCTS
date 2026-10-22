// SPDX-FileCopyrightText: Copyright Hewlett Packard Enterprise Development LP
// SPDX-License-Identifier: MIT

// ============================================================================
// Selection Unit - Best Child Selector
// 2x2 Board Accelerator Architecture
// ============================================================================

module best_child_selector (
    input  logic        clk,
    input  logic        rst_n,
    input  logic        enable,
    input  logic [15:0] ucb1_value_0,
    input  logic [15:0] ucb1_value_1,
    input  logic [15:0] ucb1_value_2,
    input  logic [15:0] ucb1_value_3,
    input  logic [3:0]  child_valid,
    
    output logic [1:0]  best_child_id,
    output logic [15:0] max_ucb1_value,
    output logic        selection_valid
);

    // Tournament comparison function
    function automatic logic [1:0] compare_and_select(
        logic [15:0] val_a, logic [15:0] val_b,
        logic [1:0] id_a, logic [1:0] id_b,
        logic valid_a, logic valid_b,
        output logic [15:0] max_val
    );
        if (!valid_a && !valid_b) begin
            max_val = 16'h0;
            return 2'h0;
        end else if (!valid_a) begin
            max_val = val_b;
            return id_b;
        end else if (!valid_b) begin
            max_val = val_a;
            return id_a;
        end else if (val_a >= val_b) begin
            max_val = val_a;
            return id_a;
        end else begin
            max_val = val_b;
            return id_b;
        end
    endfunction

    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            best_child_id   <= 2'h0;
            max_ucb1_value  <= 16'h0;
            selection_valid <= 1'b0;
        end else if (enable) begin
            logic [15:0] stage1_val_0, stage1_val_1;
            logic [1:0]  stage1_id_0, stage1_id_1;
            
            // Stage 1: Compare pairs (0,1) and (2,3)
            stage1_id_0 = compare_and_select(
                ucb1_value_0, ucb1_value_1, 
                2'h0, 2'h1,
                child_valid[0], child_valid[1],
                stage1_val_0
            );
            
            stage1_id_1 = compare_and_select(
                ucb1_value_2, ucb1_value_3,
                2'h2, 2'h3,
                child_valid[2], child_valid[3],
                stage1_val_1
            );
            
            // Stage 2: Final comparison
            best_child_id = compare_and_select(
                stage1_val_0, stage1_val_1,
                stage1_id_0, stage1_id_1,
                (child_valid[0] | child_valid[1]), (child_valid[2] | child_valid[3]),
                max_ucb1_value
            );
            
            selection_valid <= |child_valid;
        end else begin
            selection_valid <= 1'b0;
        end
    end

endmodule
