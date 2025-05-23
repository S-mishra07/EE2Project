import network
import urequests
import time

# WiFi credentials
ssid = 'MyWiFi'
password = 'Cloonmoreavenue123'

# Connect to WiFi
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

# Wait for connection
max_wait = 10
while max_wait > 0:
    status = wlan.status()
    print(f'Waiting... status = {status}')
    if status < 0 or status >= 3:
        break
    time.sleep(1)
    max_wait -= 1

# Check connection result
status_code = wlan.status()
if status_code != 3:
    print('Failed to connect')
    raise RuntimeError('WiFi connection failed')
else:
    print('Connected!')

# URL for current price
URL_PRICE = "https://icelec50015.azurewebsites.net/price "

# Prediction settings
HISTORY_TICK_COUNT = 5
previous_prices = []

# === Main Loop ===
while True:
    try:
        # Fetch current price
        response = urequests.get(URL_PRICE)
        data = response.json()
        current_tick = data['tick']	
        current_price = data['sell_price']

        # Store recent prices
        previous_prices.append(current_price)
        if len(previous_prices) > HISTORY_TICK_COUNT:
            previous_prices.pop(0)

        # Predict next price (simple average of last N prices)
        predicted_price = sum(previous_prices) / len(previous_prices)

        # Print for Thonny Plotter
        print(f"Actual: {current_price:.2f} Predicted: {predicted_price:.2f}")

        # Wait before next update
        time.sleep(1)

    except Exception as e:
        print("Error:", e)
        time.sleep(5)
