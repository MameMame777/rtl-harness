`timescale 1ns / 1ps

// Hazard unit for a classic 5-stage pipeline: forwarding selects for the two ALU operands
// and the load-use stall.
//
// What this example shows (docs/cpu.md):
//   * a purely combinational module: one always_comb, every output assigned a default
//     first, so there is no latch and no path is left unassigned
//   * forwarding priority: the EX stage (newest result) wins over the MEM stage
//   * register x0 is never forwarded (it is hard-wired to zero)
//   * a load in EX whose destination is read in ID must stall for one cycle: the data does
//     not exist yet, forwarding cannot help
module hazard_unit #(
    parameter int REG_ADDR_WIDTH = 5
) (
    // instruction in ID: source registers
    input  logic [REG_ADDR_WIDTH-1:0] id_rs1,
    input  logic [REG_ADDR_WIDTH-1:0] id_rs2,
    // instruction in EX: destination and control
    input  logic [REG_ADDR_WIDTH-1:0] ex_rd,
    input  logic                      ex_reg_write,
    input  logic                      ex_mem_read,
    // instruction in MEM: destination and control
    input  logic [REG_ADDR_WIDTH-1:0] mem_rd,
    input  logic                      mem_reg_write,
    // outputs
    output logic [               1:0] forward_a,      // fwd_sel_t
    output logic [               1:0] forward_b,      // fwd_sel_t
    output logic                      stall
);
    typedef enum logic [1:0] {
        FWD_NONE = 2'd0,  // operand comes from the register file
        FWD_EX   = 2'd1,  // operand comes from the EX/MEM result
        FWD_MEM  = 2'd2   // operand comes from the MEM/WB result
    } fwd_sel_t;

    fwd_sel_t fwd_a;
    fwd_sel_t fwd_b;
    logic     ex_writes_reg;
    logic     mem_writes_reg;

    assign ex_writes_reg  = ex_reg_write && (ex_rd != '0);
    assign mem_writes_reg = mem_reg_write && (mem_rd != '0);

    always_comb begin
        // defaults first: no forwarding, no stall
        fwd_a = FWD_NONE;
        fwd_b = FWD_NONE;
        stall = 1'b0;

        // operand A: EX has priority over MEM
        if (ex_writes_reg && (ex_rd == id_rs1)) begin
            fwd_a = FWD_EX;
        end else if (mem_writes_reg && (mem_rd == id_rs1)) begin
            fwd_a = FWD_MEM;
        end

        // operand B
        if (ex_writes_reg && (ex_rd == id_rs2)) begin
            fwd_b = FWD_EX;
        end else if (mem_writes_reg && (mem_rd == id_rs2)) begin
            fwd_b = FWD_MEM;
        end

        // load-use: the value is still being read from memory
        if (ex_mem_read && (ex_rd != '0) && ((ex_rd == id_rs1) || (ex_rd == id_rs2))) begin
            stall = 1'b1;
        end
    end

    assign forward_a = fwd_a;
    assign forward_b = fwd_b;
endmodule
