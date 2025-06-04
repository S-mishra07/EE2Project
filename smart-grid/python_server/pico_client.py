import time
#import ubinascii
#import machine
from umqtt.simple import MQTTClient

client_id = "pico" # ubinascii.hexlify(machine.unique_id()) to allocate id
broker = "18.210.146.176" # put your ip address in here as for now mosquitto is running locally
port = 1883
topic_from_server = b"server_data" # b has to be there as micropython requres byte string for mqtt topics
topic_to_server = b"pico_data"

payload = "hello from pico"

def on_message(topic, msg):
    print(f"from server: {msg.decode()}")
    # need to do something with this

mqttc = MQTTClient(client_id, broker)
mqttc.set_callback(on_message)
mqttc.connect()
mqttc.subscribe(topic_from_server)
print("connected to mqtt")

def publish_to_server():
    while True:
        mqttc.publish(topic_to_server, payload)
        print(f"sent to server: {payload}")
        mqttc.check_msg()
        time.sleep(5)

publish_to_server()
