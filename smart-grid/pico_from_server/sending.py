from flask import Flask
import serial

app = Flask(__name__)

# Open the serial port to the Pico
try:
    pico = serial.Serial('COM7', 115200, timeout=1)
except serial.SerialException as e:
    print("Error opening serial port:", e)
    pico = None

@app.route("/")
def read_from_pico():
    if pico and pico.in_waiting:
        try:
            line = pico.readline().decode('utf-8').strip()
            return f"Pico says: {line}"
        except Exception as e:
            return f"Error reading from Pico: {e}"
    return "No data available from Pico."

if __name__ == "__main__":
    app.run(port=5000)
