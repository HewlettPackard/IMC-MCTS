// Ideal external column bank. ADC inputs are sampled from captured values.
// Fixture codes represent exact noiseless products, not an analog circuit.
// SPDX-License-Identifier: MIT
    logic column_capture_valid, column_capture_ready = 1'b0;
    logic [8:0] column_capture_columns;
    logic column_bank_clear, column_bank_valid;
    logic [7:0] held_codes [0:127];
    logic [23:0] sampled_codes = '0;
    logic held_valid = 1'b0, sampled_valid = 1'b0;
    logic [3:0] held_owner = '0;
    integer held_next = 0, held_columns = 0, captured_cycle = 0;
    integer hold_index, hold_lane, hold_column, hold_count, capture_wait = 0;
    logic [71:0] hold_vector;

    always @(negedge clk) begin
        if (!column_capture_valid) capture_wait = 0;
        else if (capture_wait < 3) capture_wait = capture_wait + 1;
        column_capture_ready = rst_n && (STALL == 0 || capture_wait >= 3);
    end

    always @(posedge clk) begin
        if (!rst_n || column_bank_clear) begin
            held_valid = 1'b0;
            sampled_valid = 1'b0;
            held_next = 0;
            sampled_codes = '0;
        end else begin
            if (column_bank_valid !== held_valid) $fatal(1, "column ownership differs");
            if (column_capture_valid && !column_capture_ready)
                $fdisplay(events, "capture_stall,%0d,%0d", hold_run, cycle);
            if (array_enable) $fdisplay(events, "array_on,%0d,%0d", hold_run, cycle);
            if (column_capture_valid && column_capture_ready) begin
                if (!array_enable || held_valid || sampled_valid) $fatal(1, "capture while unavailable");
                if (column_capture_columns == 0 || column_capture_columns > 128) $fatal(1, "capture size");
                held_owner = array_id;
                held_columns = int'(column_capture_columns);
                held_next = 0;
                hold_column = 0;
                hold_index = adc_index;
                while (hold_column < held_columns) begin
                    if (hold_index >= HOLD_ADC_LIMIT) $fatal(1, "capture exceeds fixture");
                    hold_vector = adc_vectors[hold_index];
                    hold_count = int'(hold_vector[27:26]);
                    if ({array_id,row_start,row_count,input_bit,row_bits} !== hold_vector[71:36] ||
                        hold_column != int'(hold_vector[35:28]) || hold_count == 0 ||
                        hold_column + hold_count > held_columns) $fatal(1, "capture geometry/drive");
                    for (hold_lane = 0; hold_lane < hold_count; hold_lane = hold_lane + 1)
                        held_codes[hold_column + hold_lane] = hold_vector[hold_lane*8 +: 8];
                    hold_column = hold_column + hold_count;
                    hold_index = hold_index + 1;
                end
                held_valid = 1'b1;
                captured_cycle = cycle;
                $fdisplay(events, "capture,%0d,%0d,%0d,%0d", hold_run, cycle, array_id, held_columns);
            end
            if (sample_hold) begin
                if (array_enable || !held_valid || sampled_valid || array_id !== held_owner ||
                    int'(column_start) != held_next || column_count == 0 ||
                    held_next + int'(column_count) > held_columns) $fatal(1, "invalid held sample");
                sampled_codes = '0;
                for (hold_lane = 0; hold_lane < int'(column_count); hold_lane = hold_lane + 1)
                    sampled_codes[hold_lane*8 +: 8] = held_codes[held_next + hold_lane];
                held_next = held_next + int'(column_count);
                if (held_next == held_columns) held_valid = 1'b0;
                sampled_valid = 1'b1;
                $fdisplay(events, "hold_sample,%0d,%0d,%0d", hold_run, cycle, cycle-captured_cycle);
            end
            if (adc_req_valid && adc_req_ready) begin
                if (array_enable || !sampled_valid) $fatal(1, "ADC without stored sample");
                sampled_valid = 1'b0;
            end
        end
    end
