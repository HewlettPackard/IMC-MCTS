// ucb_q32_ln256_v1: 1 - mean + C*sqrt(ln(parent_visits)/child_visits).
// Exact Q17 sums, Q48 division/interpolation/root, Q32 coefficient and score.
// Valid visited counts satisfy 1 <= child <= parent < 2^32, 0 <= C <= 8.
// Ratio first; its square root overlaps the mean division. Both must complete.
// First-unvisited handling remains in the selector. Completion is held.
// PPA role: overlapped_UCB_parent_with_existing_arithmetic_and_new_control
// SPDX-License-Identifier: MIT
`default_nettype none
module imc_ucb_score_overlap (
    input logic clk,
    input logic rst_n,
    input logic score_req_valid,
    output logic score_req_ready,
    input logic [31:0] score_parent_visits,
    input logic [31:0] score_child_visits,
    input logic [63:0] score_child_value,
    input logic [63:0] score_exploration,
    output logic score_rsp_valid,
    input logic score_rsp_ready,
    output logic [63:0] score_rsp_value,
    output logic score_rsp_error,
    output logic [3:0] debug_state
);
    typedef enum logic [3:0] {
        ST_IDLE, ST_LOG, ST_RATIO_START, ST_RATIO_WAIT,
        ST_PARALLEL_START, ST_PARALLEL_WAIT, ST_SCORE, ST_RESULT
    } state_e;
    state_e state_q, state_d;
    logic [31:0] parent_q, parent_d, child_q, child_d;
    logic [48:0] value_q, value_d, mean_q, mean_d, decoded_value;
    logic [35:0] coefficient_q, coefficient_d, coefficient;
    logic [55:0] log_q, log_d, log_low, log_high;
    logic [103:0] radicand_q, radicand_d;
    logic [63:0] score_d, unused_codec_binary;
    logic error_d, codec_error, coefficient_error;
    logic [52:0] c_significand, c_floor, c_remainder, c_half, c_rounded;
    logic [5:0] c_shift;
    logic [4:0] leading;
    logic [23:0] fraction;
    logic [71:0] interpolation;
    logic [55:0] interpolated;
    logic div_start, div_done, div_error, unused_div_ready;
    logic [79:0] div_numerator, div_quotient;
    logic [31:0] unused_div_remainder;
    logic sqrt_start, sqrt_done, unused_sqrt_ready;
    logic [51:0] sqrt_root;
    logic mean_done_q, mean_done_d, root_done_q, root_done_d;
    logic [87:0] product, total;
    logic [40:0] rounded;
    logic [5:0] score_leading;
    logic [51:0] mantissa;
    logic [10:0] exponent;
    logic [63:0] encoded_score;
    integer i;

    imc_q17_codec u_value (
        .binary_value(score_child_value), .decoded_value(decoded_value),
        .decode_error(codec_error), .encoded_value(49'd0), .binary_result(unused_codec_binary)
    );
    imc_ln_table u_low (.index({1'b0, fraction[23:16]}), .value(log_low));
    imc_ln_table u_high (.index({1'b0, fraction[23:16]}+9'd1), .value(log_high));
    imc_round_divider #(.NUM_W(80), .DEN_W(32)) u_divider (
        .clk(clk), .rst_n(rst_n), .clear(1'b0), .start(div_start),
        .numerator(div_numerator), .denominator(child_q), .ready(unused_div_ready),
        .done(div_done), .error(div_error), .quotient(div_quotient), .remainder(unused_div_remainder)
    );
    imc_isqrt u_sqrt (
        .clk(clk), .rst_n(rst_n), .clear(1'b0), .start(sqrt_start),
        .radicand(radicand_q), .ready(unused_sqrt_ready), .done(sqrt_done), .root(sqrt_root)
    );
    assign score_req_ready = rst_n && state_q == ST_IDLE;
    assign score_rsp_valid = rst_n && state_q == ST_RESULT;
    assign debug_state = state_q;
    assign div_start = state_q == ST_PARALLEL_START || state_q == ST_RATIO_START;
    assign div_numerator = state_q == ST_PARALLEL_START ? {value_q, 31'd0} : {24'd0, log_q};
    assign sqrt_start = state_q == ST_PARALLEL_START;

    always_comb begin
        c_significand = {1'b1, score_exploration[51:0]};
        c_floor = '0;
        c_remainder = '0;
        c_half = '0;
        c_shift = 6'(11'd1043 - score_exploration[62:52]);
        if (score_exploration[62:52] >= 11'd990 && score_exploration[62:52] <= 11'd1026) begin
            c_floor = c_significand >> c_shift;
            c_remainder = c_significand - (c_floor << c_shift);
            c_half = 53'd1 << (c_shift - 6'd1);
        end
        c_rounded = c_floor + 53'(c_remainder > c_half || (c_remainder == c_half && c_floor[0]));
        coefficient = c_rounded[35:0];
        coefficient_error = (score_exploration[63] && score_exploration[62:0] != '0) ||
            score_exploration[62:0] > 63'h4020000000000000 || c_rounded[52:36] != '0;
        leading = '0;
        for (i = 0; i < 32; i = i + 1)
            if (parent_q[i]) leading = 5'(i);
        fraction = 24'((parent_q << (5'd31-leading)) >> 7);
        interpolation = (72'(log_high)-72'(log_low)) * {56'd0, fraction[15:0]};
        interpolated = interpolation[71:16] + 56'(interpolation[15:0] > 16'h8000 ||
            (interpolation[15:0] == 16'h8000 && interpolation[16]));
        product = sqrt_root * coefficient_q;
        total = product + {7'd0, (49'd281474976710656-mean_q), 32'd0};
        rounded = {1'b0, total[87:48]} + 41'(total[47:0] > 48'h800000000000 ||
            (total[47:0] == 48'h800000000000 && total[48]));
        score_leading = '0;
        for (i = 0; i < 40; i = i + 1)
            if (rounded[i]) score_leading = 6'(i);
        mantissa = {12'd0, rounded[39:0]} << (6'd52-score_leading);
        exponent = 11'd991 + {5'd0, score_leading};
        encoded_score = rounded == '0 ? 64'd0 : {1'b0, exponent, mantissa};

        state_d = state_q;
        parent_d = parent_q;
        child_d = child_q;
        value_d = value_q;
        mean_d = mean_q;
        coefficient_d = coefficient_q;
        log_d = log_q;
        radicand_d = radicand_q;
        score_d = score_rsp_value;
        error_d = score_rsp_error;
        mean_done_d = mean_done_q;
        root_done_d = root_done_q;
        unique case (state_q)
            ST_IDLE: if (score_req_valid) begin
                parent_d = score_parent_visits;
                child_d = score_child_visits;
                value_d = decoded_value;
                coefficient_d = coefficient;
                score_d = '0;
                error_d = 1'b0;
                mean_done_d = 1'b0;
                root_done_d = 1'b0;
                state_d = ST_LOG;
                if (codec_error || coefficient_error || score_child_visits == '0 ||
                    score_child_visits > score_parent_visits || decoded_value > {score_child_visits, 17'd0}) begin
                    state_d = ST_RESULT;
                    error_d = 1'b1;
                end
            end
            ST_LOG: begin
                log_d = 56'(leading)*56'd195103586505167 + log_low + interpolated;
                state_d = ST_RATIO_START;
            end
            ST_RATIO_START: state_d = ST_RATIO_WAIT;
            ST_RATIO_WAIT: if (div_done) begin
                radicand_d = {div_quotient[55:0], 48'd0};
                state_d = ST_PARALLEL_START;
                if (div_error || div_quotient[79:56] != '0) begin
                    error_d = 1'b1;
                    state_d = ST_RESULT;
                end
            end
            ST_PARALLEL_START: state_d = ST_PARALLEL_WAIT;
            ST_PARALLEL_WAIT: begin
                if (sqrt_done) root_done_d = 1'b1;
                if (div_done) begin
                    mean_d = div_quotient[48:0];
                    mean_done_d = 1'b1;
                end
                if (root_done_d && mean_done_d) state_d = ST_SCORE;
                if (div_done && (div_error || div_quotient > 80'd281474976710656)) begin
                    error_d = 1'b1;
                    state_d = ST_RESULT;
                end
            end
            ST_SCORE: begin
                score_d = encoded_score;
                error_d = rounded[40];
                state_d = ST_RESULT;
            end
            ST_RESULT: if (score_rsp_ready) state_d = ST_IDLE;
            default: begin
                state_d = ST_RESULT;
                error_d = 1'b1;
            end
        endcase
    end
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            state_q <= ST_IDLE;
            parent_q <= '0;
            child_q <= '0;
            value_q <= '0;
            mean_q <= '0;
            coefficient_q <= '0;
            log_q <= '0;
            radicand_q <= '0;
            mean_done_q <= 1'b0;
            root_done_q <= 1'b0;
            score_rsp_value <= '0;
            score_rsp_error <= 1'b0;
        end else begin
            state_q <= state_d;
            parent_q <= parent_d;
            child_q <= child_d;
            value_q <= value_d;
            mean_q <= mean_d;
            coefficient_q <= coefficient_d;
            log_q <= log_d;
            radicand_q <= radicand_d;
            mean_done_q <= mean_done_d;
            root_done_q <= root_done_d;
            score_rsp_value <= score_d;
            score_rsp_error <= error_d;
        end
    end
endmodule
`default_nettype wire
