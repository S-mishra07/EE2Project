import urequests
import ujson
import time

start_url = "http://192.168.3.96:8000/latest_data"
end_url = "http://192.168.3.96:8000/insert_data"

data = {
    "sensor": "sun_intensity",
    "value": 89.3,
    "unit": "lux"
}

def send_data(data):
    print("Attempting to send data...")
    try:
        response = urequests.post(
            end_url,  
            data=ujson.dumps(data),
            headers={'Content-Type': 'application/json'}
        )
        print("POST Response status code:", response.status_code)
        print("POST Response content:", response.text)
        response.close()
        print("Data sent successfully.")
    except Exception as e:
        print("Error sending data:", e)

def get_latest_data():
    print("Attempting to get latest data...")
    try:
        response = urequests.get(start_url) 
        print("GET Response status code:", response.status_code)
        if response.status_code == 200:
            latest_data = response.json()
            print("Latest data from server:", latest_data)
        else:
            print("Failed to fetch latest data, status code:", response.status_code)
        response.close()
        print("Data fetched successfully.")
    except Exception as e:
        print("Error getting data:", e)

send_data(data)
time.sleep(2) 
get_latest_data()

