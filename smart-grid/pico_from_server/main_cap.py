from machine import Pin, I2C, ADC, PWM, Timer
import time
import network
from umqtt.simple import MQTTClient
import json

# PWM setup
pwm = PWM(Pin(9))
pwm.freq(100000)
min_pwm = 0
max_pwm = 64536

# Global constants and PI gains
P_ref_constant = 0.1  # Initial dummy power reference
SHUNT_OHMS = 0.10
kp = 100
ki = 300

# ADC inputs
va_pin = ADC(Pin(28))
vb_pin = ADC(Pin(26))

# I2C for INA219
ina_i2c = I2C(0, scl=Pin(1), sda=Pin(0), freq=2400000)

# INA219 class
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

# PI and saturation helpers
def saturate(signal, upper, lower):
    return max(min(signal, upper), lower)

# Initialize INA219 and settle control loop
ina = ina219(SHUNT_OHMS, 64, 5)
ina.configure()

i_err_int = 0
stable_count = 0
elapsed_count = 0
STABLE_THRESHOLD = 0.01
STABLE_REQUIRED_COUNT = 100
MAX_SETTLE_CYCLES = 300  # 300 * 10ms = 3 seconds

print("Settling control loop before connecting to Wi-Fi...")

while stable_count < STABLE_REQUIRED_COUNT and elapsed_count < MAX_SETTLE_CYCLES:
    va = 1.017 * (12490 / 2490) * 3.3 * (va_pin.read_u16() / 65536)
    vb = 1.015 * (12490 / 2490) * 3.3 * (vb_pin.read_u16() / 65536)

    P_ref = P_ref_constant
    P_ref = saturate(P_ref, 3, -3)

    if vb < 0.1:
        i_ref = 0
    else:
        i_ref = P_ref / vb
        i_ref = saturate(i_ref, 0.35, -0.35)

    iL = ina.vshunt() / SHUNT_OHMS
    i_err = i_ref - iL
    i_err_int += i_err
    i_err_int = saturate(i_err_int, 500, -200)

    i_pi_out = (kp * i_err) + (ki * i_err_int)
    pwm_out = saturate(i_pi_out, max_pwm, min_pwm)
    duty = int(65536 - pwm_out)
    pwm.duty_u16(duty)

    print(f"[SETTLING] Cycle={elapsed_count}, Va={va:.3f} V, Vb={vb:.3f} V, iL={iL:.3f} A, "
          f"i_ref={i_ref:.3f} A, i_err={i_err:.4f}, int_err={i_err_int:.4f}, duty={duty}")

    if abs(i_err) < STABLE_THRESHOLD:
        stable_count += 1
    else:
        stable_count = 0

    elapsed_count += 1
    time.sleep(0.01)

print("Control loop settling phase completed. Proceeding to Wi-Fi and MQTT...")

# Wi-Fi Connection
ssid = 'MyWiFi'
password = 'Cloonmoreavenue123'
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

max_wait = 10
while max_wait > 0:
    status = wlan.status()
    print(f'Waiting... status = {status}')
    if status < 0 or status >= 3:
        break
    time.sleep(1)
    max_wait -= 1

status_code = wlan.status()
if status_code != 3:
    print(f'Failed to connect. Status = {status_code}')
    raise RuntimeError('WiFi connection failed')
else:
    print('Connected successfully!')
    print('IP Address:', wlan.ifconfig()[0])

# MQTT Setup
client_id = "SMPS_capacitor"
broker = "192.168.72.60"
port = 1883
topic_to_server = "cap_data"
topic_from_algorithm = b"algorithm_data"

def on_message(topic, msg):
    global P_ref_constant
    message = msg.decode()
    print(f"Received message: {message}")
    try:
        parts = message.strip().split()
        if len(parts) >= 2:
            command = parts[0].lower()
            power_str = parts[1]
            if power_str.endswith('j'):
                power_value = float(power_str[:-1])
            else:
                power_value = float(power_str)
            if command == "charging":
                P_ref_constant = power_value / 5
                print(f"Set P_ref_constant to {P_ref_constant} W for charging")
            elif command == "discharging":
                P_ref_constant = -power_value / 5
                print(f"Set P_ref_constant to {P_ref_constant} W for discharging")
            else:
                P_ref_constant = 0
                print(f"Unknown command: {command}")
    except (ValueError, IndexError) as e:
        print(f"Error parsing message '{message}': {e}")

mqttc = MQTTClient(client_id, broker)
mqttc.set_callback(on_message)
mqttc.connect()
mqttc.subscribe(topic_from_algorithm)
print("Connected to MQTT and subscribed to topic.")

# Timer and control loop
timer_elapsed = 0
count = 0

def tick(t):
    global timer_elapsed
    timer_elapsed = 1

loop_timer = Timer(mode=Timer.PERIODIC, freq=1000, callback=tick)

last_publish_time = time.ticks_ms()
publish_interval = 1000

while True:
    mqttc.check_msg()

    if timer_elapsed == 1:
        va = 1.017 * (12490 / 2490) * 3.3 * (va_pin.read_u16() / 65536)
        vb = 1.015 * (12490 / 2490) * 3.3 * (vb_pin.read_u16() / 65536)

        P_ref = saturate(P_ref_constant, 3, -3)

        if vb < 0.1:
            i_ref = 0
        else:
            i_ref = P_ref / vb
            i_ref = saturate(i_ref, 0.35, -0.35)

        iL = ina.vshunt() / SHUNT_OHMS
        i_err = i_ref - iL
        i_err_int += i_err
        i_err_int = saturate(i_err_int, 500, -200)

        i_pi_out = (kp * i_err) + (ki * i_err_int)
        pwm_out = saturate(i_pi_out, max_pwm, min_pwm)
        duty = int(65536 - pwm_out)
        pwm.duty_u16(duty)

        count += 1
        timer_elapsed = 0

        if count >= 100:
            print(f"[LOOP] Va={va:.3f} V, Vb={vb:.3f} V, iL={iL:.3f} A, i_ref={i_ref:.3f} A, "
                  f"i_err={i_err:.4f}, int_err={i_err_int:.4f}, P_ref={P_ref:.3f} W, duty={duty}")
            count = 0
        
        data = { "Vout": f"{vb:0.3f}",
                     "Iout": f"{iL:0.3f}"
                }
    
        payload = json.dumps(data)
    
        current_time = time.ticks_ms()
        if time.ticks_diff(current_time, last_publish_time) >= publish_interval:
            mqttc.publish(topic_to_server, payload)
            print(f"sent to server: {payload}")
            mqttc.check_msg()
            last_publish_time = current_time


