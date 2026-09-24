`timescale 1ns / 1ps

// Smoke-test design for the harness loop (lint -> sim -> CI). Deliberately tiny.
// An up counter with a synchronous active-low reset and an enable.
module smoke_counter #(
    parameter int WIDTH = 8
) (
    input  logic             clk,
    input  logic             rst_n,
    input  logic             en,
    output logic [WIDTH-1:0] count,
    output logic             wrap
);
    logic [WIDTH-1:0] count_next;

    always_comb begin
        count_next = count;
        if (en) begin
            count_next = count + WIDTH'(1);
        end
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            count <= '0;
        end else begin
            count <= count_next;
        end
    end

    assign wrap = en && (count == '1);
endmodule
