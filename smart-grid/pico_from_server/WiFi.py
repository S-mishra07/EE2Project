import time
import network

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
