from machine import Pin, ADC, PWM
from PID import PID

# ────────────────────────────────
# Hardware / calibration constants
# ────────────────────────────────
VREF        = 3.3                      # Pico ADC reference (V)
CAL         = 1.026                    # Empirical gain-error correction
DIV_RATIO   = 12490 / 2490             # Vin/Vout divider ratio
RSENSE      = 1.0                      # Ω of the current-sense resistor (edit if different!)

TARGET_I_A  = 0.4                     # Constant current target (A)
SETPOINT_V  = TARGET_I_A * RSENSE      # Sense-resistor voltage that equals 0.40 A

# ────────────────────────────────
# I/O setup
# ────────────────────────────────
vin_pin  = ADC(Pin(27))
vout_pin = ADC(Pin(28))
vret_pin = ADC(Pin(26))                # Vsense (across shunt)

pwm      = PWM(Pin(0))
pwm.freq(100_000)                      # 100 kHz switching
pwm_en   = Pin(1, Pin.OUT)

# ────────────────────────────────
# PID controller
# ────────────────────────────────
pid = PID(Kp=0.2, Ki=10, Kd=0,
          setpoint=SETPOINT_V, scale='ms')  # scale='ms' → PID returns duty-cycle 0–1

def saturate(raw_duty):
    """Clamp duty-cycle to protect the converter and the ADC rails."""
    return max(100, min(62_500, raw_duty))

# ────────────────────────────────
# Main control loop
# ────────────────────────────────
counter = 0
while True:
    pwm_en.value(1)                    # Enable PWM output

    # ♦ Read and scale voltages
    vin  = CAL * DIV_RATIO * VREF * (vin_pin.read_u16()  / 65_536)
    vout = CAL * DIV_RATIO * VREF * (vout_pin.read_u16() / 65_536)
    vret = VREF * ((vret_pin.read_u16() - 350) / 65_536)   # offset-trimmed Vsense

    # ♦ PID regulation
    duty_f = pid(vret)                 # 0.0–1.0 float
    duty_u16 = saturate(int(duty_f * 65_536))
    pwm.duty_u16(duty_u16)

    # ♦ Status every ~2 000 iterations
    counter += 1
    if counter >= 2_000:
        isense = vret / RSENSE
        print(f"Vin   = {vin:0.3f} V")
        print(f"Vout  = {vout:0.3f} V")
        print(f"Vsense= {vret:0.3f} V  →  I = {isense:0.3f} A")
        print(f"Duty  = {duty_u16}")
        counter = 0

