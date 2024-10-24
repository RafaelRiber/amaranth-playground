from amaranth import *

from amaranth_boards.icebreaker import ICEBreakerPlatform
from amaranth_boards.versa_ecp5 import VersaECP5Platform
from amaranth_boards.tang_nano import TangNanoPlatform
from amaranth_boards.arty_a7 import ArtyA7_100Platform

from .blinky import Blinky


class Toplevel(Elaboratable):
    def elaborate(self, platform):
        m = Module()

        m.submodules.blinky = blinky = Blinky(frequency=platform.default_clk_frequency)
        m.d.comb += platform.request("led", 0).o.eq(blinky.led)

        return m


def build_ice40():
    ICEBreakerPlatform().build(Toplevel())


def build_ecp5():
    VersaECP5Platform().build(Toplevel())


def build_gowin():
    TangNanoPlatform().build(Toplevel())

def build_arty100():
    ArtyA7_100Platform().build(Toplevel())
