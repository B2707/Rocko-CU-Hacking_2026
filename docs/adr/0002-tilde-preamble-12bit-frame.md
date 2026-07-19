# Frame format, tilde preamble plus 4 one hot flags

The final build carries one explorer device, so a per device frequency
identity scheme was not needed. Instead the frame identifies the message
type directly: an 8 bit tilde preamble (`01111110`) for frame sync, followed
by 4 flag bits for fire, trapped, lost, and injured. The flags are one hot
and can combine, so a single frame can represent more than one thing
happening at once.

Consequences: airtime is about 12 seconds per frame at a 1.0 second bit
time, the flag space covers every emergency class the on device classifier
produces plus an SOS combination, and there is no separate identity or
location field since there is only one device to identify.

There is no CRC or check bits in the frame. Corruption at the bit level is
handled by repetition instead of detection: emergency frames repeat 3 times
with a 3 second gap, and the surface decoder takes a majority vote across
the repeats.

Superseded from the original plan: an earlier version of this decision used
a 9 bit frame (a start bit plus 4 bit equipment code plus 4 bit location
code) and identified devices by carrier frequency rather than by bits. The
final build simplified to the single device, one hot flag design above.
