# Pico ADC streamer (MicroPython). Copy onto the Pico as main.py.
# Wire: signal (0-3.3 V!) -> GP26, ground -> GND. USB to the laptop.
# Prints one ADC reading per line at a fixed rate; live_scope.py plots them.
from machine import ADC
import time

adc = ADC(26)                      # GP26 = ADC0
RATE = 200                         # samples per second (live_scope.py must match)
PERIOD_US = 1_000_000 // RATE

next_t = time.ticks_us()
while True:
    print(adc.read_u16())          # 0..65535
    next_t = time.ticks_add(next_t, PERIOD_US)
    dt = time.ticks_diff(next_t, time.ticks_us())
    if dt > 0:
        time.sleep_us(dt)
