import urequests

print("Sun intensity")

start_url = ""
end_url = ""


def send_data(data, url):
    headers = {'Content-Type': 'application/json'}
    payload = data
    
    try:
        response = urequests.post(url, json=payload, headers=headers)
        print("Server response:", response.text)
        response.close()
        
    except Exception as e:
        print("Failed to send data:", e)
    
response = urequests.get(start_url)

if response.status_code == 200:
    data = response.json()
    for key in data:
        print(f"{key}: {data1[key]}")
    send_data(data, end_url)
    
else:
    print("Error:", response.status_code)

response.close()



