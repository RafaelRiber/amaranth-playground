from amaranth import *
from amaranth.lib import stream, wiring
from amaranth.lib.wiring import In, Out
from amaranth.lib.cdc  import FFSynchronizer
from amaranth.lib.fifo import SyncFIFOBuffered
from amaranth.sim import Simulator, Period
from stream_helpers import *
import math
from enum import Enum




class I2S_Receiver(wiring.Component):
    def __init__(self, sample_width):
        self.sample_width = sample_width
        super().__init__({
            # Inputs
            "sclk" : In(1),
            "ws" : In(1),
            "sd_rx" : In(1),

            # Outputs
            #"l_data_rx" : Out(stream.Signature(unsigned(sample_width))),
            "r_data_rx" : Out(stream.Signature(unsigned(sample_width)))

        })
    def elaborate(self, platform):
        m = Module()

        # Detect edges on the `sclk` input:
        sclk_reg = Signal()
        sclk_edge = ~sclk_reg & self.sclk
        m.d.sync += sclk_reg.eq(self.sclk)

        # Capture `sd_rx` and bits into payloads:
        count = Signal(range(self.sample_width))
        data = Signal(self.sample_width)
        done = Signal()

        # Right Channel only for now
        with m.If(~self.ws):
            m.d.sync += count.eq(0)
        with m.Elif(sclk_edge):
            m.d.sync += count.eq(count + 1)
            m.d.sync += data.eq(Cat(self.sd_rx, data))
            m.d.sync += done.eq(count == self.sample_width - 1)

        # Push assembled payloads into the pipeline:
        with m.If(done & (~self.r_data_rx.valid | self.r_data_rx.ready)):
            m.d.sync += self.r_data_rx.payload.eq(data)
            m.d.sync += self.r_data_rx.valid.eq(1)
            m.d.sync += done.eq(0)
        with m.Elif(self.r_data_rx.ready):
            m.d.sync += self.r_data_rx.valid.eq(0)
        # Payload is discarded if `done & self.r_data_rx.valid & ~self.r_data_rx.ready`.

        return m

class I2S_Transmitter(wiring.Component):
    def __init__(self, sample_width):
        self.sample_width = sample_width
        super().__init__({
            # Inputs
            "ws" : In(1),
            #"l_data_tx" : In(stream.Signature(unsigned(sample_width))),
            "r_data_tx" : In(stream.Signature(unsigned(sample_width))),

            # Outputs
            "sclk" : Out(1),
            "sd_tx" : Out(1)
        })
    def elaborate(self, platform):
        m = Module()
        count = Signal(range(self.sample_width + 1))
        data = Signal(self.sample_width)
        
        with m.If(~self.ws):
            m.d.sync += count.eq(0)
            m.d.sync += self.sclk.eq(1)
        with m.Elif(count != 0):
            m.d.comb += self.r_data_tx.ready.eq(0)
            m.d.sync += self.sclk.eq(~self.sclk)
            with m.If(self.sclk):
                m.d.sync += data.eq(Cat(0, data))
                m.d.sync += self.sd_tx.eq(data[-1])
            with m.Else():
                m.d.sync += count.eq(count - 1)
        with m.Else():
            m.d.comb += self.r_data_tx.ready.eq(1)
            with m.If(self.r_data_tx.valid):
                m.d.sync += count.eq(self.sample_width)
                m.d.sync += data.eq(self.r_data_tx.payload)

        return m

def test_i2s_transmitter():
    dut = I2S_Transmitter(sample_width=4)
    async def testbench_input(ctx):
        await stream_put(ctx, dut.r_data_tx, 0b1010)
    
    async def testbench_output(ctx):
        await ctx.tick()
        ctx.set(dut.ws, 1)
        for index, expected_bit in enumerate([1, 0, 1, 0]):
            _, sd_tx = await ctx.posedge(dut.sclk).sample(dut.sd_tx)
            assert sd_tx == expected_bit, \
                f"bit {index}: {sd_tx} != {expected_bit} (expected)"
        ctx.set(dut.ws, 0)
        await ctx.tick()

    sim = Simulator(dut)
    sim.add_clock(Period(MHz=1))
    sim.add_testbench(testbench_input)
    sim.add_testbench(testbench_output)
    with sim.write_vcd("i2s_tx.vcd"):
        sim.run()

def test_i2s_receiver():
    dut = I2S_Receiver(sample_width=16)

    async def testbench_input(ctx):
        await ctx.tick()
        ctx.set(dut.ws, 1)
        await ctx.tick()
        for bit in [1, 0, 1, 0, 0, 1, 1, 1, 1, 0, 1, 0, 0, 1, 1, 1]:
            ctx.set(dut.sd_rx, bit)
            ctx.set(dut.sclk, 0)
            await ctx.tick()
            ctx.set(dut.sclk, 1)
            await ctx.tick()
        ctx.set(dut.ws, 0)
        # For later testing with 2 channels
        # await ctx.tick()
        # for bit in [1, 0, 1, 0, 0, 1, 1, 1, 1, 0, 1, 0, 0, 1, 1, 1]:
        #     ctx.set(dut.sd_rx, bit)
        #     ctx.set(dut.sclk, 0)
        #     await ctx.tick()
        #     ctx.set(dut.sclk, 1)
        #     await ctx.tick()
        # ctx.set(dut.ws, 1)

    async def testbench_output(ctx):
        expected_word = 0b1010011110100111
        payload = await stream_get(ctx, dut.r_data_rx)
        assert (payload & 0xff) == (expected_word & 0xff), \
            f"{payload & 0xff:08b} != {expected_word & 0xff:08b} (expected)"

    sim = Simulator(dut)
    sim.add_clock(Period(MHz=1))
    sim.add_testbench(testbench_input)
    sim.add_testbench(testbench_output)
    with sim.write_vcd("i2s_rx.vcd"):
        sim.run()

if __name__ == "__main__":
    test_i2s_transmitter()