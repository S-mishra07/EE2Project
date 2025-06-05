from machine import Pin, I2C, ADC, PWM, Timer

# ADC inputs
va_pin = ADC(Pin(28))
vb_pin = ADC(Pin(26))
vpot_pin = ADC(Pin(27))

# Switches
OL_CL_pin = Pin(12, Pin.IN, Pin.PULL_UP)
BU_BO_pin = Pin(2, Pin.IN, Pin.PULL_UP)

# I2C for INA219
ina_i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=2400000)

# PWM setup
pwm = PWM(Pin(9))
pwm.freq(100000)
min_pwm = 0
max_pwm = 64536

# Global state
timer_elapsed = 0
count = 0
first_run = 1
SHUNT_OHMS = 0.10
OC = 0

# PI Controller
i_ref = 0.0
i_err = 0
i_err_int = 0
kp = 100
ki = 300

# V-pot filter buffer
v_pot_filt = [0] * 100
v_pot_index = 0

def saturate(signal, upper, lower): 
    return max(min(signal, upper), lower)

def tick(t): 
    global timer_elapsed
    timer_elapsed = 1

class ina219: 
    REG_CONFIG = 0x00
    REG_SHUNTVOLTAGE = 0x01
    REG_BUSVOLTAGE = 0x02
    REG_CALIBRATION = 0x05

    def __init__(self, sr, address, maxi):
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

# Main loop
while True:
    if first_run:
        ina = ina219(SHUNT_OHMS, 64, 5)
        ina.configure()
        loop_timer = Timer(mode=Timer.PERIODIC, freq=1000, callback=tick)
        first_run = 0

    if timer_elapsed == 1:
        va = 1.017 * (12490 / 2490) * 3.3 * (va_pin.read_u16() / 65536)
        vb = 1.015 * (12490 / 2490) * 3.3 * (vb_pin.read_u16() / 65536)

        vpot_in = 1.026 * 3.3 * (vpot_pin.read_u16() / 65536)
        v_pot_filt[v_pot_index] = vpot_in
        v_pot_index = (v_pot_index + 1) % 100
        vpot = sum(v_pot_filt) / 100

        # Map vpot range (0V–3.3V) to -0.35A to +0.35A
        i_ref = saturate(((vpot - 1.65) / 1.65) * 0.35, 0.35, -0.35)

        iL = ina.vshunt() / SHUNT_OHMS
        i_err = i_ref - iL
        i_err_int += i_err
        i_err_int = saturate(i_err_int, 10000, -10000)

        i_pi_out = (kp * i_err) + (ki * i_err_int)
        pwm_out = saturate(i_pi_out, max_pwm, min_pwm)



        duty = int(65536 - pwm_out)
        pwm.duty_u16(duty)

        count += 1
        timer_elapsed = 0

        if count >= 100:
            print("Va = {:.3f} V".format(va))
            print("Vb = {:.3f} V".format(vb))
            print("iL = {:.3f} A".format(iL))
            print("i_ref = {:.3f} A".format(i_ref))
            print("PWM Duty = {}".format(duty))
            count = 0
