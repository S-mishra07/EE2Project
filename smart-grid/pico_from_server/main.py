from machine import Pin, ADC, PWM
from PID import PID
import time
import json
import network
from umqtt.simple import MQTTClient

ssid = 'MyWiFi'
password = 'Cloonmoreavenue123'

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

# Wait for connection with status checks
max_wait = 10
while max_wait > 0:
    status = wlan.status()
    print(f'Waiting... status = {status}')
    if status < 0 or status >= 3:
        break
    time.sleep(1)
    max_wait -= 1

# Print result
status_code = wlan.status()
if status_code != 3:
    print(f'Failed to connect. Status = {status_code}')
    raise RuntimeError('WiFi connection failed')
else:
    print('Connected successfully!')
    print('IP Address:', wlan.ifconfig()[0])

client_id = "pico" # make sure to give unique client id
broker = "192.168.135.60" # put your ip address in here as for now mosquitto is running locally
port = 1883
topic_from_server = b"server_data" # b has to be there as micropython requres byte string for mqtt topics
topic_to_server = b"pico_data" # make sure to allocate unique topic

def on_message(topic, msg):
    print(f"from server: {msg.decode()}")
    # need to do something with this
    
mqttc = MQTTClient(client_id, broker)
mqttc.set_callback(on_message)
mqttc.connect()
mqttc.subscribe(topic_from_server)
print("connected to mqtt")

# ────────────────────────────────
# Hardware / calibration constants
# ────────────────────────────────
VREF        = 3.3
CAL         = 1.026
DIV_RATIO   = 12490 / 2490
RSENSE      = 1.02

TARGET_P_W  = 0.7                      # Adjust to safe power level
SETPOINT_P  = TARGET_P_W

ALPHA       = 0.1                      # Smoothing factor for EMA filter

# ────────────────────────────────
# I/O setup
# ────────────────────────────────
vin_pin  = ADC(Pin(27))
vout_pin = ADC(Pin(28))
vret_pin = ADC(Pin(26))

pwm      = PWM(Pin(0))
pwm.freq(100_000)
pwm_en   = Pin(1, Pin.OUT)

# ────────────────────────────────
# PID controller
# ────────────────────────────────
pid = PID(Kp=0.3, Ki=1.5, Kd=0.05, setpoint=SETPOINT_P, scale='ms')

def saturate(raw_duty):
    return max(100, min(62_500, raw_duty))

# ────────────────────────────────
# Helper: Exponential Moving Average Filter
# ────────────────────────────────
def ema_filter(new_val, prev_val):
    return ALPHA * new_val + (1 - ALPHA) * prev_val

# ────────────────────────────────
# Main loop
# ────────────────────────────────
counter = 0
vin_filt = vout_filt = vret_filt = 0
prev_duty = 0

last_publish_time = time.ticks_ms()
publish_interval = 1000

while True:
    pwm_en.value(1)

    # Read and scale
    vin_raw  = CAL * DIV_RATIO * VREF * (vin_pin.read_u16()  / 65_536)
    vout_raw = CAL * DIV_RATIO * VREF * (vout_pin.read_u16() / 65_536)
    vret_raw = VREF * ((vret_pin.read_u16() - 350) / 65_536)

    # Apply filtering
    vin_filt  = ema_filter(vin_raw, vin_filt)
    vout_filt = ema_filter(vout_raw, vout_filt)
    vret_filt = ema_filter(vret_raw, vret_filt)

    isense = vret_filt / RSENSE
    power = vout_filt * isense

    # PID regulation
    duty_f = pid(power)
    duty_f_smooth = 0.1 * duty_f + 0.9 * (prev_duty / 65_536)  # smooth duty
    prev_duty = saturate(int(duty_f_smooth * 65_536))
    pwm.duty_u16(prev_duty)

    # Debug print
    counter += 1
    if counter >= 1000:
        print(f"Vin    = {vin_filt:0.3f} V")
        print(f"Vout   = {vout_filt:0.3f} V")
        print(f"Vsense = {vret_filt:0.3f} V")
        print(f"Iout = {isense:0.3f} A")
        print(f"Power  = {power:0.3f} W")
        print(f"Duty   = {prev_duty}")
        counter = 0

    data = { "Vin": f"{vin_filt:0.3f}",
                "Vout": f"{vout_filt:0.3f}",
                "Iout": f"{isense:0.3f}"
            }
    
    payload = json.dumps(data)
    
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, last_publish_time) >= publish_interval:
        mqttc.publish(topic_to_server, payload)
        print(f"sent to server: {payload}")
        mqttc.check_msg()
        last_publish_time = current_time
        
    time.sleep_ms(4)  # slow down the loop to reduce flickering