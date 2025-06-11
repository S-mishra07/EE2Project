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

client_id = "Yellow_LED" # make sure to give unique client id
broker = "18.210.146.176" # put your ip address in here as for now mosquitto is running locally
port = 1883
topic_from_server = b"demand_data" # b has to be there as micropython requres byte string for mqtt topics
topic_to_server = b"pico_data" # make sure to allocate unique topic

demand_value = 0
TARGET_P_W = 0.5

def on_message(topic, msg):
    global TARGET_P_W, demand_value
    message = json.loads(msg.decode())
    print(f"from server: {message}")#
    demand_value = message["demand"]["demand"]
    TARGET_P_W = demand_value/4
    pid.setpoint = TARGET_P_W
    print(demand_value)
    print(TARGET_P_W)

mqttc = MQTTClient(client_id, broker)
mqttc.set_callback(on_message)
mqttc.connect()
mqttc.subscribe(topic_from_server)
print("connected to mqtt")

VREF        = 3.3
CAL         = 1.026
DIV_RATIO   = 12490 / 2490
RSENSE      = 1.02

ALPHA       = 0.1              

vin_pin  = ADC(Pin(27))
vout_pin = ADC(Pin(28))
vret_pin = ADC(Pin(26))

pwm      = PWM(Pin(0))
pwm.freq(100_000)
pwm_en   = Pin(1, Pin.OUT)

pid = PID(Kp=0.3, Ki=1.5, Kd=0.05, setpoint=TARGET_P_W, scale='ms')

def saturate(raw_duty):
    return max(100, min(62_500, raw_duty))

def ema_filter(new_val, prev_val):
    return ALPHA * new_val + (1 - ALPHA) * prev_val

counter = 0
vin_filt = vout_filt = vret_filt = 0
prev_duty = 0

last_publish_time = time.ticks_ms()
publish_interval = 1000

while True:
    pwm_en.value(1)

    vin_raw  = CAL * DIV_RATIO * VREF * (vin_pin.read_u16()  / 65_536)
    vout_raw = CAL * DIV_RATIO * VREF * (vout_pin.read_u16() / 65_536)
    vret_raw = VREF * ((vret_pin.read_u16() - 350) / 65_536)

    vin_filt  = ema_filter(vin_raw, vin_filt)
    vout_filt = ema_filter(vout_raw, vout_filt)
    vret_filt = ema_filter(vret_raw, vret_filt)

    isense = vret_filt / RSENSE
    power = vout_filt * isense

    duty_f = pid(power)
    duty_f_smooth = 0.1 * duty_f + 0.9 * (prev_duty / 65_536)
    prev_duty = saturate(int(duty_f_smooth * 65_536))
    pwm.duty_u16(prev_duty)

    counter += 1
    if counter >= 1000:
        #print(f"Vin    = {vin_filt:0.3f} V")
        #print(f"Vout   = {vout_filt:0.3f} V")
        #print(f"Vsense = {vret_filt:0.3f} V")
        #print(f"Iout = {isense:0.3f} A")
        #print(f"Power  = {power:0.3f} W")
        #print(f"Duty   = {prev_duty}")
        counter = 0

    data = { "Vin": f"{vin_filt:0.3f}",
                "Vout": f"{vout_filt:0.3f}",
                "Iout": f"{isense:0.3f}"
            }
    
    payload = json.dumps(data)
    
    current_time = time.ticks_ms()
    if time.ticks_diff(current_time, last_publish_time) >= publish_interval:
        mqttc.publish(topic_to_server, payload)
        #print(f"sent to server: {payload}")
        mqttc.check_msg()
        last_publish_time = current_time
        
    time.sleep_ms(4)  