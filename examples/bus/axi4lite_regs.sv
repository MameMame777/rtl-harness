`timescale 1ns / 1ps

// AXI4-Lite register slave: NUM_REGS read/write registers, word addressed from 0.
//
// What this example shows (docs/bus.md):
//   * a three-process state machine with a typed enum (state register, next-state logic,
//     output logic) for each of the write and read sides
//   * every case has a default; out-of-range accesses answer SLVERR instead of hanging
//   * write strobes are honoured byte by byte; address and data channels may arrive in
//     either order
//   * $clog2 for every derived width, ALL_CAPS parameters, lower_snake_case signals
module axi4lite_regs #(
    parameter int ADDR_WIDTH = 8,
    parameter int DATA_WIDTH = 32,
    parameter int NUM_REGS   = 4
) (
    input  logic                                    clk,
    input  logic                                    rst_n,
    // write address / data / response
    input  logic                                    s_axil_awvalid,
    output logic                                    s_axil_awready,
    input  logic [  ADDR_WIDTH-1:0]                 s_axil_awaddr,
    input  logic                                    s_axil_wvalid,
    output logic                                    s_axil_wready,
    input  logic [  DATA_WIDTH-1:0]                 s_axil_wdata,
    input  logic [DATA_WIDTH/8-1:0]                 s_axil_wstrb,
    output logic                                    s_axil_bvalid,
    input  logic                                    s_axil_bready,
    output logic [             1:0]                 s_axil_bresp,
    // read address / data
    input  logic                                    s_axil_arvalid,
    output logic                                    s_axil_arready,
    input  logic [  ADDR_WIDTH-1:0]                 s_axil_araddr,
    output logic                                    s_axil_rvalid,
    input  logic                                    s_axil_rready,
    output logic [  DATA_WIDTH-1:0]                 s_axil_rdata,
    output logic [             1:0]                 s_axil_rresp,
    // register file
    output logic [    NUM_REGS-1:0][DATA_WIDTH-1:0] reg_out
);
    localparam int         BYTES       = DATA_WIDTH / 8;
    localparam int         ADDR_LSB    = $clog2(BYTES);
    localparam int         IDX_WIDTH   = (NUM_REGS > 1) ? $clog2(NUM_REGS) : 1;  // register index
    localparam logic [1:0] RESP_OKAY   = 2'b00;
    localparam logic [1:0] RESP_SLVERR = 2'b10;

    typedef enum logic [1:0] {
        WR_IDLE,  // collecting the address and data beats
        WR_RESP   // holding the write response
    } wr_state_t;
    typedef enum logic {
        RD_IDLE,
        RD_RESP
    } rd_state_t;

    wr_state_t wr_state, wr_state_next;
    rd_state_t rd_state, rd_state_next;
    logic aw_pending, w_pending;  // beat captured, write not done yet
    logic [IDX_WIDTH-1:0] aw_idx_q, aw_idx;  // captured / effective register index
    logic aw_ok_q, aw_ok;  // captured / effective "address accepted"
    logic [DATA_WIDTH-1:0] w_data_q, w_data;  // captured / effective write data
    logic [BYTES-1:0] w_strb_q, w_strb;
    logic [DATA_WIDTH-1:0] rdata_q;
    logic [1:0] bresp_q, rresp_q;
    logic aw_fire, w_fire, ar_fire, wr_go;
    logic aw_ok_now, ar_ok;

    assign aw_fire = s_axil_awvalid && s_axil_awready;
    assign w_fire = s_axil_wvalid && s_axil_wready;
    assign ar_fire = s_axil_arvalid && s_axil_arready;
    assign wr_go = (aw_pending || aw_fire) && (w_pending || w_fire);
    // An access is accepted when it is word aligned and hits an implemented register.
    assign aw_ok_now = (s_axil_awaddr[ADDR_LSB-1:0] == '0)
                       && (int'(s_axil_awaddr[ADDR_WIDTH-1:ADDR_LSB]) < NUM_REGS);
    assign ar_ok     = (s_axil_araddr[ADDR_LSB-1:0] == '0)
                       && (int'(s_axil_araddr[ADDR_WIDTH-1:ADDR_LSB]) < NUM_REGS);
    // The address and data beats may arrive together or in either order: the write uses
    // the beat arriving THIS cycle when there is one, else the captured copy.
    assign aw_idx = aw_fire ? s_axil_awaddr[ADDR_LSB+:IDX_WIDTH] : aw_idx_q;
    assign aw_ok = aw_fire ? aw_ok_now : aw_ok_q;
    assign w_data = w_fire ? s_axil_wdata : w_data_q;
    assign w_strb = w_fire ? s_axil_wstrb : w_strb_q;

    // ---- write side: next state ---------------------------------------------------------
    always_comb begin
        wr_state_next = wr_state;
        unique case (wr_state)
            WR_IDLE: begin
                if (wr_go) begin
                    wr_state_next = WR_RESP;
                end
            end
            WR_RESP: begin
                if (s_axil_bready) begin
                    wr_state_next = WR_IDLE;
                end
            end
            default: wr_state_next = WR_IDLE;
        endcase
    end

    // ---- write side: outputs ------------------------------------------------------------
    always_comb begin
        s_axil_awready = (wr_state == WR_IDLE) && !aw_pending;
        s_axil_wready  = (wr_state == WR_IDLE) && !w_pending;
        s_axil_bvalid  = (wr_state == WR_RESP);
        s_axil_bresp   = bresp_q;
    end

    // ---- write side: registers ----------------------------------------------------------
    always_ff @(posedge clk) begin
        if (!rst_n) begin
            wr_state   <= WR_IDLE;
            aw_pending <= 1'b0;
            w_pending  <= 1'b0;
            aw_idx_q   <= '0;
            aw_ok_q    <= 1'b0;
            w_data_q   <= '0;
            w_strb_q   <= '0;
            bresp_q    <= RESP_OKAY;
            reg_out    <= '0;
        end else begin
            wr_state <= wr_state_next;
            if (aw_fire) begin
                aw_idx_q   <= s_axil_awaddr[ADDR_LSB+:IDX_WIDTH];
                aw_ok_q    <= aw_ok_now;
                aw_pending <= 1'b1;
            end
            if (w_fire) begin
                w_data_q  <= s_axil_wdata;
                w_strb_q  <= s_axil_wstrb;
                w_pending <= 1'b1;
            end
            if (wr_state == WR_IDLE && wr_go) begin
                aw_pending <= 1'b0;
                w_pending  <= 1'b0;
                bresp_q    <= aw_ok ? RESP_OKAY : RESP_SLVERR;
                for (int b = 0; b < BYTES; b++) begin
                    if (aw_ok && w_strb[b]) begin
                        reg_out[aw_idx][b*8+:8] <= w_data[b*8+:8];
                    end
                end
            end
        end
    end

    // ---- read side ----------------------------------------------------------------------
    always_comb begin
        rd_state_next = rd_state;
        unique case (rd_state)
            RD_IDLE: begin
                if (ar_fire) begin
                    rd_state_next = RD_RESP;
                end
            end
            RD_RESP: begin
                if (s_axil_rready) begin
                    rd_state_next = RD_IDLE;
                end
            end
            default: rd_state_next = RD_IDLE;
        endcase
    end

    always_comb begin
        s_axil_arready = (rd_state == RD_IDLE);
        s_axil_rvalid  = (rd_state == RD_RESP);
        s_axil_rdata   = rdata_q;
        s_axil_rresp   = rresp_q;
    end

    always_ff @(posedge clk) begin
        if (!rst_n) begin
            rd_state <= RD_IDLE;
            rdata_q  <= '0;
            rresp_q  <= RESP_OKAY;
        end else begin
            rd_state <= rd_state_next;
            if (ar_fire) begin
                rdata_q <= ar_ok ? reg_out[s_axil_araddr[ADDR_LSB+:IDX_WIDTH]] : '0;
                rresp_q <= ar_ok ? RESP_OKAY : RESP_SLVERR;
            end
        end
    end
endmodule
