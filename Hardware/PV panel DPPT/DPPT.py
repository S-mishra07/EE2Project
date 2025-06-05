from machine import Pin, I2C, ADC, PWM, Timer
import utime

# Set up some pin allocations for the Analogues and switches
va_pin = ADC(Pin(28))
vb_pin = ADC(Pin(26))
vpot_pin = ADC(Pin(27))
OL_CL_pin = Pin(12, Pin.IN, Pin.PULL_UP)
BU_BO_pin = Pin(2, Pin.IN, Pin.PULL_UP)

# Set up the I2C for the INA219 chip for current sensing
ina_i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=2400000)

# PWM settings
pwm = PWM(Pin(9))
pwm.freq(100000)
min_pwm = 20000
max_pwm = 50000
pwm_out = min_pwm

# Control logic variables
timer_elapsed = 0
count = 0
first_run = 1

# INA219 shunt resistance
SHUNT_OHMS = 0.10

# MPPT state variables
prev_power = 0
mppt_step = 1000
mppt_dir = 1
current_duty = min_pwm
prev_duty = min_pwm

# Saturation function
def saturate(signal, upper, lower):
    if signal > upper:
        signal = upper
    if signal < lower:
        signal = lower
    return signal

# Adaptive MPPT step size
def adaptive_step_size(prev_power, output_power, step):
    power_diff = abs(output_power - prev_power)
    if power_diff < 0.05:
        step = max(step // 2, 10)
    else:
        step = min(step * 2, 1000)
    return step

# Timer callback
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

    def vshunt(self):
        reg_bytes = ina_i2c.readfrom_mem(self.address, self.REG_SHUNTVOLTAGE, 2)
        reg_value = int.from_bytes(reg_bytes, 'big')
        if reg_value > 2**15:
            sign = -1
            for i in range(16):
                reg_value ^= (1 << i)
        else:
            sign = 1
        return float(reg_value) * 1e-5 * sign

    def vbus(self):
        reg_bytes = ina_i2c.readfrom_mem(self.address, self.REG_BUSVOLTAGE, 2)
        reg_value = int.from_bytes(reg_bytes, 'big') >> 3
        return float(reg_value) * 0.004

    def configure(self):
        ina_i2c.writeto_mem(self.address, self.REG_CONFIG, b'\x19\x9F')
        ina_i2c.writeto_mem(self.address, self.REG_CALIBRATION, b'\x00\x00')

# Initialize file for logging
with open('/Data.csv', 'w') as file:
    file.write('Time_ms,Power\n')
    start_time = utime.ticks_ms()

    while True:
        if first_run:
            ina = ina219(SHUNT_OHMS, 64, 5)
            ina.configure()
            first_run = 0
            loop_timer = Timer(mode=Timer.PERIODIC, freq=500, callback=tick)

        if timer_elapsed == 1:
            va = 1.017 * (12490 / 2490) * 3.3 * (va_pin.read_u16() / 65536)
            vb = 1.015 * (12490 / 2490) * 3.3 * (vb_pin.read_u16() / 65536)
            Vshunt = ina.vshunt()
            iL = Vshunt / SHUNT_OHMS

            output_power = round(vb * iL, 5)
            prev_power = round(prev_power, 5)
            mppt_step = adaptive_step_size(prev_power, output_power, mppt_step)

            if output_power > prev_power:
                prev_power = output_power
                prev_duty = current_duty
                current_duty += mppt_step * mppt_dir
            else:
                mppt_dir *= -1
                current_duty = prev_duty + mppt_step * mppt_dir

            current_duty = saturate(current_duty, max_pwm, min_pwm)
            duty = 65536 - current_duty
            pwm.duty_u16(duty)

            utime.sleep_ms(25)

            count += 1
            timer_elapsed = 0
            
            if count > 20:
                elapsed_time = utime.ticks_ms() - start_time

                print(f"Time = {elapsed_time} ms")
                print(f"Va = {va:.3f} V")
                print(f"Vb = {vb:.3f} V")
                print(f"Vshunt = {Vshunt:.5f} V")
                print(f"iL = {iL:.3f} A")
                print(f"Duty = {duty}")
                print(f"Power = {output_power:.5f} W\n")

                file.write(f"{elapsed_time},{output_power:.5f}\n")
                count = 0


