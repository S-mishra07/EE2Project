import paho.mqtt.client as mqtt
import threading
import time

stop_event = threading.Event()
broker = "18.210.146.176"
port = 1883
client_id   = "fastapi"
topic_from_pico = "pico_data"
topic_to_pico = "server_data"

payload = "hello from server"

def on_connect(client, *_):
    client.subscribe(topic_from_pico)
    print("connected to MQTT")

def on_message(client, userdata, msg):
    print(f"from pico: {msg.payload.decode()}")
    # need to do something with this

mqttc = mqtt.Client(client_id=client_id, protocol=mqtt.MQTTv311)
mqttc.on_connect = on_connect
mqttc.on_message = on_message
mqttc.connect(broker, 1883, keepalive=60)

def publish_to_pico():
    while not stop_event.is_set():
        mqttc.publish(topic_to_pico, payload, retain=False)
        print(f"sent to pico: {payload}")
        time.sleep(5)

mqttc.loop_start()
publisher = threading.Thread(target=publish_to_pico).start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("Stopping...")
    stop_event.set()  
    publisher.join()
    mqttc.loop_stop()
    print("Stopped")