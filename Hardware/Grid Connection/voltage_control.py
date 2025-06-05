from machine import Pin, I2C, ADC, PWM, Timer

# Set up some pin allocations for the Analogues and switches
va_pin = ADC(Pin(28))
vb_pin = ADC(Pin(26))
vpot_pin = ADC(Pin(27))
OL_CL_pin = Pin(12, Pin.IN, Pin.PULL_UP)
BU_BO_pin = Pin(2, Pin.IN, Pin.PULL_UP)

# Set up the I2C for the INA219 chip for current sensing
ina_i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=2400000)

# PWM setup
pwm = PWM(Pin(9))
pwm.freq(100000)
min_pwm = 0
max_pwm = 64536
pwm_out = min_pwm
pwm_ref = 30000

# Error signals
trip = 0
OC = 0

# Moving average filter buffer for potentiometer
v_pot_filt = [0]*100
v_pot_index = 0

# PID controller constants
v_ref = 9.0  # Constant reference voltage
v_err = 0
v_err_int = 0
v_pi_out = 0
kp = 100
ki = 30

# Basic logic flags
global timer_elapsed
timer_elapsed = 0
count = 0
first_run = 1

# Shunt resistance value
global SHUNT_OHMS
SHUNT_OHMS = 0.10

# Saturation function
def saturate(signal, upper, lower): 
    if signal > upper:
        signal = upper
    if signal < lower:
        signal = lower
    return signal

# Timer callback
def tick(t): 
    global timer_elapsed
    timer_elapsed = 1

# INA219 sensor class
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
                reg_value = (reg_value ^ (1 << i))
        else:
            sign = 1
        return (float(reg_value) * 1e-5 * sign)
        
    def vbus(self):
        reg_bytes = ina_i2c.readfrom_mem(self.address, self.REG_BUSVOLTAGE, 2)
        reg_value = int.from_bytes(reg_bytes, 'big') >> 3
        return float(reg_value) * 0.004
        
    def configure(self):
        ina_i2c.writeto_mem(self.address, self.REG_CONFIG, b'\x19\x9F')  # PG = /8
        ina_i2c.writeto_mem(self.address, self.REG_CALIBRATION, b'\x00\x00')

# Main loop
while True:
    if first_run:
        ina = ina219(SHUNT_OHMS, 64, 5)
        ina.configure()
        first_run = 0
        loop_timer = Timer(mode=Timer.PERIODIC, freq=1000, callback=tick)
    
    if timer_elapsed == 1:  # 1kHz control loop
        va = 1.0*(12490/2490)*3.3*(va_pin.read_u16()/65536)
        vb = 1.0*(12490/2490)*3.3*(vb_pin.read_u16()/65536)
        
        vpot_in = 1.026*3.3*(vpot_pin.read_u16()/65536)
        v_pot_filt[v_pot_index] = vpot_in
        v_pot_index = (v_pot_index + 1) % 100
        vpot = sum(v_pot_filt)/100
        
        Vshunt = ina.vshunt()
        CL = OL_CL_pin.value()
        BU = BU_BO_pin.value()
        
        iL = Vshunt / SHUNT_OHMS
        
        # Constant voltage mode (no droop)
        v_err = v_ref - vb
        v_err_int += v_err
        v_err_int = saturate(v_err_int, 10000, -10000)
        v_pi_out = (kp * v_err) + (ki * v_err_int)
        
        pwm_out = saturate(v_pi_out, max_pwm, min_pwm)
        duty = int(65536 - pwm_out)
        pwm.duty_u16(duty)
        
        count += 1
        timer_elapsed = 0
        
        if count > 100:
            print("Va = {:.3f}".format(va))
            print("Vb = {:.3f}".format(vb))
            print("Vpot = {:.3f}".format(vpot))
            print("iL = {:.3f}".format(iL))
            print("OC = {:b}".format(OC))
            print("duty = {:d}".format(duty))
            print("v_ref = {:.3f}".format(v_ref))
            print("v_err = {:.3f}".format(v_err))
            print("v_err_int = {:.3f}".format(v_err_int))
            count = 0

