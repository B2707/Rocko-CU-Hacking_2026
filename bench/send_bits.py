# Send a raw bit pattern through the coil: 1 = tone (coil polarity flips at TONE_HZ),
# 0 = silence. Repeats forever with a gap so the receiver can spot the start.
# Run on the Pi that drives the L298N:  python3 send_bits.py
import time

BITS = "10101110"    # the pattern to send
BIT_SECONDS = 1.0    # airtime per bit
TONE_HZ = 4          # polarity flips per second during a "1" (AC field = visible to TMR)
GAP_SECONDS = 3.0    # silence between repeats

# --- adapt ONLY these two functions to however you already drive the coil ---
import RPi.GPIO as GPIO
IN1, IN2, ENA = 23, 24, 18            # L298N pins (BCM numbering) - change to yours
GPIO.setmode(GPIO.BCM)
GPIO.setup([IN1, IN2, ENA], GPIO.OUT)
pwm = GPIO.PWM(ENA, 1000)
pwm.start(0)

def tone(seconds):
    """Alternate coil polarity at TONE_HZ for `seconds`."""
    pwm.ChangeDutyCycle(100)
    half = 1.0 / (2 * TONE_HZ)
    end = time.time() + seconds
    state = False
    while time.time() < end:
        GPIO.output(IN1, state)
        GPIO.output(IN2, not state)
        state = not state
        time.sleep(half)

def silence(seconds):
    pwm.ChangeDutyCycle(0)
    time.sleep(seconds)
# ---------------------------------------------------------------------------

try:
    while True:
        print("sending", BITS)
        for b in BITS:
            tone(BIT_SECONDS) if b == "1" else silence(BIT_SECONDS)
        silence(GAP_SECONDS)
except KeyboardInterrupt:
    pwm.stop()
    GPIO.cleanup()
