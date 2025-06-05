from machine import Pin, I2C, ADC, PWM, Timer

# Pin setup
vb_pin = ADC(Pin(26))  # Only use Vb for boost
vpot_pin = ADC(Pin(27))
OL_CL_pin = Pin(12, Pin.IN, Pin.PULL_UP)
BU_BO_pin = Pin(2, Pin.IN, Pin.PULL_UP)

# I2C for INA219 current sensor
ina_i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=2400000)

# PWM setup
pwm = PWM(Pin(9))
pwm.freq(100000)
min_pwm = 1000
max_pwm = 64536
pwm_out = min_pwm

# Potentiometer filtering
v_pot_filt = [0] * 100
v_pot_index = 0

# State control
global timer_elapsed
timer_elapsed = 0
count = 0
first_run = 1
global SHUNT_OHMS
SHUNT_OHMS = 0.10

# MPPT control variables
prev_power = 0
prev_voltage = 0
delta_duty = 1000
mppt_direction = 1

# Saturation
def saturate(signal, upper, lower):
    return max(min(signal, upper), lower)

# Timer ISR
def tick(t):
    global timer_elapsed
    timer_elapsed = 1

# INA219 class
class ina219:
    REG_CONFIG = 0x00
    REG_SHUNTVOLTAGE = 0x01
    REG_BUSVOLTAGE = 0x02
    REG_POWER = 0x03
    REG_CURRENT = 0x04
    REG_CALIBRATION = 0x05

    def __init__(self, sr, address, maxi):
        self.address = address
        self.shunt = sr

    def vshunt(icur):
        reg_bytes = ina_i2c.readfrom_mem(icur.address, icur.REG_SHUNTVOLTAGE, 2)
        reg_value = int.from_bytes(reg_bytes, 'big')
        if reg_value > 2**15:
            sign = -1
            for i in range(16):
                reg_value ^= (1 << i)
        else:
            sign = 1
        return float(reg_value) * 1e-5 * sign

    def vbus(ivolt):
        reg_bytes = ina_i2c.readfrom_mem(ivolt.address, ivolt.REG_BUSVOLTAGE, 2)
        reg_value = int.from_bytes(reg_bytes, 'big') >> 3
        return float(reg_value) * 0.004

    def configure(conf):
        ina_i2c.writeto_mem(conf.address, conf.REG_CONFIG, b'\x19\x9F')
        ina_i2c.writeto_mem(conf.address, conf.REG_CALIBRATION, b'\x00\x00')

# Main loop
while True:
    if first_run:
        ina = ina219(SHUNT_OHMS, 64, 5)
        ina.configure()
        first_run = 0
        loop_timer = Timer(mode=Timer.PERIODIC, freq=1000, callback=tick)

    if timer_elapsed == 1:
        vb = 1.015 * (12490 / 2490) * 3.3 * (vb_pin.read_u16() / 65536)
        vpot_in = 1.026 * 3.3 * (vpot_pin.read_u16() / 65536)
        v_pot_filt[v_pot_index] = vpot_in
        v_pot_index = (v_pot_index + 1) % 100
        vpot = sum(v_pot_filt) / 100

        Vshunt = ina.vshunt()
        CL = OL_CL_pin.value()
        BU = BU_BO_pin.value()
        iL = Vshunt / SHUNT_OHMS

        if CL == 1 and BU == 0:  # Boost + Closed Loop
            power = vb * iL
            if power > prev_power:
                mppt_direction = 1 if vb > prev_voltage else -1
            else:
                mppt_direction = -1 if vb > prev_voltage else 1

            pwm_out += mppt_direction * delta_duty
            pwm_out = saturate(pwm_out, max_pwm, min_pwm)

            prev_power = power
            prev_voltage = vb

            duty = int(65536 - pwm_out)
            pwm.duty_u16(duty)

        timer_elapsed = 0
        count += 1

        if count > 100:
            print("Vb = {:.3f}".format(vb))
            print("Vpot = {:.3f}".format(vpot))
            print("iL = {:.3f}".format(iL))
            print("CL = {:b}".format(CL))
            print("BU = {:b}".format(BU))
            print("Power = {:.3f}".format(power))
            print("duty = {:d}".format(duty))
            count = 0

