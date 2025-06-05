from machine import Pin, I2C, ADC, PWM, Timer

# ADCs
vb_pin = ADC(Pin(26))

# PWM for Boost Converter
pwm = PWM(Pin(9))
pwm.freq(100000)

# I2C for INA219 Current Sensor
ina_i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=2400000)

# INA219 Class (Simplified for Vshunt Only)
class INA219:
    REG_SHUNTVOLTAGE = 0x01
    def __init__(self, shunt_resistance, address=64):
        self.address = address
        self.shunt = shunt_resistance
    def vshunt(self):
        reg_bytes = ina_i2c.readfrom_mem(self.address, self.REG_SHUNTVOLTAGE, 2)
        reg_value = int.from_bytes(reg_bytes, 'big')
        if reg_value > 0x7FFF:
            reg_value -= 0x10000
        return float(reg_value) * 1e-5

# Saturation helper
def saturate(signal, upper, lower):
    return min(max(signal, lower), upper)

# Global Configs
SHUNT_OHMS = 0.10
min_pwm = 0
max_pwm = 60000
pwm_out = 40000

# MPPT Vars
prev_power = 0
prev_vb = 0
step = 500
perturb_dir = 1

# Timer flag
timer_elapsed = False
def tick(timer):
    global timer_elapsed
    timer_elapsed = True

# Setup INA219 and Timer
ina = INA219(SHUNT_OHMS)
loop_timer = Timer(mode=Timer.PERIODIC, freq=10, callback=tick)  # 10Hz MPPT loop

# Main Loop
while True:
    if timer_elapsed:
        timer_elapsed = False

        vb = 1.015 * (12490/2490) * 3.3 * (vb_pin.read_u16()/65536)  # Vb reading
        Vshunt = ina.vshunt()
        iL = -(Vshunt / SHUNT_OHMS)
        power = vb * iL

        if power > prev_power:
            pwm_out += step * perturb_dir
        else:
            perturb_dir *= -1  # Reverse direction
            pwm_out += step * perturb_dir

        pwm_out = saturate(pwm_out, max_pwm, min_pwm)
        pwm.duty_u16(int(pwm_out))

        prev_power = power
        prev_vb = vb

        # Debug Print
        print("Vb = {:.3f} V, iL = {:.3f} A, P = {:.3f} W, Duty = {:d}".format(vb, iL, power, int(pwm_out)))

