from machine import Pin, I2C, ADC, PWM, Timer
import time
import os

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

# Control variables
timer_elapsed = 0
count = 0
first_run = 1
SHUNT_OHMS = 0.10

# PI Controller
i_ref = 0.0
i_err = 0
i_err_int = 0
kp = 100
ki = 300

# Logging
log_file = None
log_started = False
log_ended = False

# Timing
start_time = 0
CHARGE_DURATION_MS = 18000       # 20 seconds charge
DISCHARGE_DURATION_MS = 30000    # 25 seconds discharge

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
        start_time = time.ticks_ms()
        first_run = 0

    if timer_elapsed == 1:
        current_time = time.ticks_ms()
        elapsed_time = time.ticks_diff(current_time, start_time)

        # Determine phase: charge or discharge
        if elapsed_time < CHARGE_DURATION_MS:
            i_ref = 0.35  # Charge with max current
        elif elapsed_time < (CHARGE_DURATION_MS + DISCHARGE_DURATION_MS):
            i_ref = -0.25  # Discharge with max negative current

            # Start logging if not already
            if not log_started:
                try:
                    log_file = open("discharge_data.csv", "w")
                    log_file.write("time_ms,voltage_Va,voltage_Vb,current_A,power_W\n")
                    log_started = True
                    print("Logging started during discharge...")
                except Exception as e:
                    print("Error opening file:", e)

            # Measure and log
            va = 1.017 * (12490 / 2490) * 3.3 * (va_pin.read_u16() / 65536)
            vb = 1.015 * (12490 / 2490) * 3.3 * (vb_pin.read_u16() / 65536)
            iL = ina.vshunt() / SHUNT_OHMS
            power = va * iL
            timestamp = elapsed_time - CHARGE_DURATION_MS

            if log_file:
                try:
                    log_file.write("{},{:.4f},{:.4f},{:.4f},{:.4f}\n".format(
                        timestamp, va, vb, iL, power))
                except Exception as e:
                    print("Write error:", e)

        # End logging
        elif not log_ended:
            if log_file:
                try:
                    log_file.close()
                    print("Logging ended. Data saved to 'discharge_data.csv'")
                except Exception as e:
                    print("Error closing file:", e)
            log_ended = True

        # PI Control
        va = 1.017 * (12490 / 2490) * 3.3 * (va_pin.read_u16() / 65536)
        iL = ina.vshunt() / SHUNT_OHMS
        i_err = i_ref - iL
        i_err_int += i_err
        i_err_int = saturate(i_err_int, 10000, -10000)
        i_pi_out = (kp * i_err) + (ki * i_err_int)
        pwm_out = saturate(i_pi_out, max_pwm, min_pwm)
        duty = int(65536 - pwm_out)
        pwm.duty_u16(duty)

        # Optional live print
        if count % 100 == 0:
            print("t = {:.1f}s | i_ref = {:.2f} | iL = {:.3f} A | duty = {}".format(
                elapsed_time / 1000, i_ref, iL, duty))

        timer_elapsed = 0
        count += 1
