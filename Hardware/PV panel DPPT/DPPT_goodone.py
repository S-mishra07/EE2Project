from machine import Pin, I2C, ADC, PWM, Timer

# --- Pin Setup ---
vb_pin = ADC(Pin(26))  # Port B: input source
va_pin = ADC(Pin(28))  # Port A: output bus/load
vpot_pin = ADC(Pin(27))  # Optional tuning pot

# --- I2C Setup for INA219 ---
ina_i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=2400000)

# --- PWM Setup ---
pwm = PWM(Pin(9))  # PWM output for Boost switch
pwm.freq(100000)
min_pwm = 0
max_pwm = 60000  # Boost safety limit
duty = 30000  # Initial duty

# --- MPPT Variables ---
prev_power = 0
prev_duty = duty
duty_step = 500
mppt_dir = 1

# --- Moving average filter for pot ---
v_pot_filt = [0] * 100
v_pot_index = 0

# --- Control flow flags ---
timer_elapsed = 0
count = 0
first_run = 1

# --- Shunt resistor ---
SHUNT_OHMS = 0.10

# --- Helper functions ---
def saturate(val, upper, lower):
    return max(min(val, upper), lower)

def tick(t):
    global timer_elapsed
    timer_elapsed = 1

# --- INA219 class ---
class ina219:
    REG_CONFIG = 0x00
    REG_SHUNTVOLTAGE = 0x01
    REG_BUSVOLTAGE = 0x02
    REG_POWER = 0x03
    REG_CURRENT = 0x04
    REG_CALIBRATION = 0x05

    def __init__(self, sr, address):
        self.address = address
        self.shunt = sr

    def vshunt(self):
        reg_bytes = ina_i2c.readfrom_mem(self.address, self.REG_SHUNTVOLTAGE, 2)
        reg_value = int.from_bytes(reg_bytes, 'big')
        if reg_value > 2**15:
            reg_value = (~reg_value + 1) & 0xFFFF
            sign = -1
        else:
            sign = 1
        return float(reg_value) * 1e-5 * sign

    def configure(self):
        ina_i2c.writeto_mem(self.address, self.REG_CONFIG, b'\x19\x9F')
        ina_i2c.writeto_mem(self.address, self.REG_CALIBRATION, b'\x00\x00')


# --- Main Loop ---
while True:
    if first_run:
        # INA219 + timer setup
        ina = ina219(SHUNT_OHMS, 64)
        ina.configure()
        loop_timer = Timer(mode=Timer.PERIODIC, freq=1000, callback=tick)
        first_run = 0

    if timer_elapsed == 1:
        # Read voltages
        vb = 1.015 * (12490 / 2490) * 3.3 * (vb_pin.read_u16() / 65536)  # Source (Port B)
        va = 1.017 * (12490 / 2490) * 3.3 * (va_pin.read_u16() / 65536)  # Bus (Port A)

        # Filter pot input
        vpot_in = 1.026 * 3.3 * (vpot_pin.read_u16() / 65536)
        v_pot_filt[v_pot_index] = vpot_in
        v_pot_index = (v_pot_index + 1) % 100
        vpot = sum(v_pot_filt) / 100

        # Read current (boost = negative shunt)
        Vshunt = ina.vshunt()
        iL = -(Vshunt / SHUNT_OHMS)

        # --- MPPT (P&O Algorithm) ---
        power = vb * iL  # Power from input (Port B)

        if power > prev_power:
            mppt_dir = 1 if duty > prev_duty else -1
        else:
            mppt_dir = -1 if duty > prev_duty else 1

        prev_duty = duty
        duty += mppt_dir * duty_step
        duty = saturate(duty, max_pwm, min_pwm)

        pwm.duty_u16(duty)  # Boost = direct duty (not inverted)
        prev_power = power

        timer_elapsed = 0
        count += 1

        # --- Debug output ---
        if count >= 100:
            print("VB (Source) = {:.3f} V".format(vb))
            print("VA (Bus)    = {:.3f} V".format(va))
            print("iL          = {:.3f} A".format(iL))
            print("Power       = {:.3f} W".format(power))
            print("Duty        = {}".format(duty))
            count = 0

