`timescale 1ns / 1ps

// Skid buffer: a two-slot elastic buffer for a valid/ready stream.
//
// What this example shows (docs/bus.md):
//   * s_ready is a REGISTER (it only reports whether the skid slot is free), so a chain of
//     these blocks never builds a long combinational ready path
//   * a beat that arrives while the output is stalled is caught in the skid slot; nothing is
//     dropped and nothing is duplicated
//   * one always_ff for the registers, assign/always_comb for everything else, '0 resets
module skid_buffer #(
    parameter int WIDTH = 32
) (
    input  logic             clk,
    input  logic             rst_n,
    // upstream
    input  logic             s_valid,
    output logic             s_ready,
    input  logic [WIDTH-1:0] s_data,
    // downstream
    output logic             m_valid,
    input  logic             m_ready,
    output logic [WIDTH-1:0] m_data
);
    logic             skid_valid;  // the skid slot holds a beat
    logic [WIDTH-1:0] skid_data;
    logic             out_valid;  // the output register holds a beat
    logic [WIDTH-1:0] out_data;
    logic             out_free;  // the output register can take a new beat this cycle
    logic             in_fire;  // an upstream beat is accepted this cycle

    assign s_ready  = !skid_valid;
    assign m_valid  = out_valid;
    assign m_data   = out_data;
    assign out_free = !out_valid || m_ready;
    assign in_fire  = s_valid && s_ready;

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            skid_valid <= 1'b0;
            skid_data  <= '0;
            out_valid  <= 1'b0;
            out_data   <= '0;
        end else begin
            // Output register: refill from the skid slot first, else from the input.
            if (out_free) begin
                if (skid_valid) begin
                    out_valid <= 1'b1;
                    out_data  <= skid_data;
                end else begin
                    out_valid <= in_fire;
                    if (in_fire) begin
                        out_data <= s_data;
                    end
                end
            end
            // Skid slot: drained into the output register, or filled while the output stalls.
            if (skid_valid) begin
                if (out_free) begin
                    skid_valid <= 1'b0;
                end
            end else if (in_fire && !out_free) begin
                skid_valid <= 1'b1;
                skid_data  <= s_data;
            end
        end
    end
endmodule
