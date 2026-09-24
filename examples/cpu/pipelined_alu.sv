`timescale 1ns / 1ps

// Three-stage pipelined ALU: register the operands (stage 1), compute (stage 2), register
// the result (stage 3). Latency is 3 cycles, throughput one operation per cycle.
//
// What this example shows (docs/cpu.md):
//   * a valid bit travels with the data through every stage (in_valid -> s1 -> s2 -> out)
//   * stage registers are named <stage>_<signal> (s1_a, s2_result, ...)
//   * the operation decode is a unique case with a default, so no latch and no X on an
//     unknown opcode
//   * widths derive from WIDTH ($clog2 for the shift amount), no magic numbers
module pipelined_alu #(
    parameter int WIDTH = 32
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             in_valid,
    input  logic [      2:0] in_op,       // alu_op_t encoding
    input  logic [WIDTH-1:0] in_a,
    input  logic [WIDTH-1:0] in_b,
    output logic             out_valid,
    output logic [WIDTH-1:0] out_result,
    output logic             out_zero
);
    localparam int SHAMT_WIDTH = $clog2(WIDTH);

    typedef enum logic [2:0] {
        OP_ADD = 3'd0,
        OP_SUB = 3'd1,
        OP_AND = 3'd2,
        OP_OR  = 3'd3,
        OP_XOR = 3'd4,
        OP_SLL = 3'd5,
        OP_SRL = 3'd6,
        OP_SLT = 3'd7
    } alu_op_t;

    // stage 1: registered operands
    logic    s1_valid;
    alu_op_t s1_op;
    logic [WIDTH-1:0] s1_a, s1_b;
    // stage 2: registered result
    logic             s2_valid;
    logic [WIDTH-1:0] s2_result;
    logic [WIDTH-1:0] alu_result;  // combinational result of stage 2

    always_comb begin
        alu_result = '0;
        unique case (s1_op)
            OP_ADD:  alu_result = s1_a + s1_b;
            OP_SUB:  alu_result = s1_a - s1_b;
            OP_AND:  alu_result = s1_a & s1_b;
            OP_OR:   alu_result = s1_a | s1_b;
            OP_XOR:  alu_result = s1_a ^ s1_b;
            OP_SLL:  alu_result = s1_a << s1_b[SHAMT_WIDTH-1:0];
            OP_SRL:  alu_result = s1_a >> s1_b[SHAMT_WIDTH-1:0];
            OP_SLT:  alu_result = WIDTH'(s1_a < s1_b);
            default: alu_result = '0;
        endcase
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            s1_valid   <= 1'b0;
            s1_op      <= OP_ADD;
            s1_a       <= '0;
            s1_b       <= '0;
            s2_valid   <= 1'b0;
            s2_result  <= '0;
            out_valid  <= 1'b0;
            out_result <= '0;
        end else begin
            // stage 1
            s1_valid <= in_valid;
            if (in_valid) begin
                s1_op <= alu_op_t'(in_op);
                s1_a  <= in_a;
                s1_b  <= in_b;
            end
            // stage 2
            s2_valid <= s1_valid;
            if (s1_valid) begin
                s2_result <= alu_result;
            end
            // stage 3
            out_valid <= s2_valid;
            if (s2_valid) begin
                out_result <= s2_result;
            end
        end
    end

    assign out_zero = out_valid && (out_result == '0);
endmodule
