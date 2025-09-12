# FILE: /home/pi/final_gateway.py
import time, pyrebase, cv2, os
from paho.mqtt.client import *
from seeed_dht import DHT
from grove.display.grove_lcd import *
from grove.gpio import GPIO
from datetime import datetime

# --- Hardware & System Config ---
DHT_PIN = 22; BUZZER_PIN = 5; FAN_RELAY_PIN = 16; LOCK_RELAY_PIN = 18
TEMP_THRESHOLD = 28.0; LOCK_PULSE_DURATION = 2.0
CAPTURE_DIR = os.path.join(os.path.expanduser('~'), 'captures')
os.makedirs(CAPTURE_DIR, exist_ok=True)

# --- Firebase Configuration ---
config = {
    "apiKey": "AIzaSyBn2HqgrwqL7hMXI3cd7jB0HvdELCT3xSw",
    "authDomain": "iot-school-e8b0b.firebaseapp.com",
    "databaseURL": "https://iot-school-e8b0b-default-rtdb.asia-southeast1.firebasedatabase.app",
    "storageBucket": "iot-school-e8b0b.appspot.com"
}

# --- MQTT Configuration ---
MQTT_BROKER = "localhost"
MQTT_TOPIC_DOOR = "server-room/01/status/door"
MQTT_TOPIC_COMMAND_LOCK = "server-room/01/commands/lock"

# --- Initialization ---
print("Initializing Firebase...")
firebase = pyrebase.initialize_app(config)
db = firebase.database()
print("Initializing hardware peripherals...")
sensor = DHT("11", DHT_PIN); buzzer = GPIO(BUZZER_PIN, GPIO.OUT)
fan_relay = GPIO(FAN_RELAY_PIN, GPIO.OUT); lock_relay = GPIO(LOCK_RELAY_PIN, GPIO.OUT)
print("Initializing camera...")
camera = cv2.VideoCapture(0)
time.sleep(1) # CRITICAL FIX: Give the camera time to initialize.
print("Camera initialized.")

# --- Core Functions ---
def update_firebase_status(temp, humi):
    status_data = {"timestamp": int(time.time()), "temperature": temp, "humidity": humi, "fan_on": bool(fan_relay.read())}
    try: db.child("system_status").set(status_data)
    except Exception as e: print(f"Error updating Firebase status: {e}")

def log_event_to_firebase(event_type, level, message, image_file=None):
    log_data = {"timestamp": int(time.time()), "type": event_type, "level": level, "message": message}
    if image_file: log_data['imageFile'] = image_file
    try: db.child("event_logs").push(log_data); print(f"Firebase event logged: {message}")
    except Exception as e: print(f"Error logging event to Firebase: {e}")

def capture_evidence():
    ret, frame = camera.read()
    if ret:
        filename = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.jpg"
        filepath = os.path.join(CAPTURE_DIR, filename)
        cv2.imwrite(filepath, frame)
        print(f"Evidence captured and saved to {filepath}")
        return filename
    else: print("CRITICAL FAILURE: Could not read frame from camera."); return None

def log_sensor_history(temp, humi):
    history_data = {"timestamp": int(time.time()), "temperature": temp, "humidity": humi}
    try: db.child("sensor_history").push(history_data)
    except Exception as e: print(f"Error logging sensor history: {e}")

def control_fan(current_temp):
    if current_temp > TEMP_THRESHOLD and not fan_relay.read(): fan_relay.write(1); log_event_to_firebase("FAN_CONTROL", "INFO", "Fan turned ON")
    elif current_temp <= TEMP_THRESHOLD and fan_relay.read(): fan_relay.write(0); log_event_to_firebase("FAN_CONTROL", "INFO", "Fan turned OFF")

def trigger_alarm(): buzzer.write(1); time.sleep(1.5); buzzer.write(0)
def pulse_lock(): log_event_to_firebase("LOCK_CONTROL", "INFO", "Unlock command received."); lock_relay.write(1); time.sleep(LOCK_PULSE_DURATION); lock_relay.write(0)

# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc):
    if rc == 0: print("Connected to MQTT Broker."); client.subscribe([(MQTT_TOPIC_DOOR, 0), (MQTT_TOPIC_COMMAND_LOCK, 0)])
    else: print(f"Failed to connect to MQTT, return code {rc}")

def on_message(client, userdata, msg):
    payload = msg.payload.decode("utf-8")
    print(f"MQTT Rx - Topic: {msg.topic} | Payload: {payload}")
    if msg.topic == MQTT_TOPIC_DOOR and payload == "OPEN":
        trigger_alarm(); image_filename = capture_evidence()
        log_event_to_firebase("DOOR_ALERT", "CRITICAL", "Door has been opened!", image_file=image_filename)
    elif msg.topic == MQTT_TOPIC_COMMAND_LOCK and payload == "UNLOCK": pulse_lock()

# --- Main Program ---
def main():
    client = Client(); client.on_connect = on_connect; client.on_message = on_message
    client.connect(MQTT_BROKER, 1883, 60); client.loop_start()
    setText_norefresh("System Booting..."); time.sleep(2)
    buzzer.write(0); fan_relay.write(0); lock_relay.write(0)
    last_sensor_read = 0; last_history_log = 0
    print("System is running.")
    try:
        while True:
            current_time = time.time()
            if current_time - last_sensor_read > 5:
                humi, temp = sensor.read()
                if humi is not None and temp is not None:
                    setText_norefresh("Temp: {:.1f}\u00b0C\nHumi: {:.1f}%".format(temp, humi))
                    control_fan(temp); update_firebase_status(temp, humi)
                    last_sensor_read = current_time
                else: setText_norefresh("Sensor Error...")
            if current_time - last_history_log > 60:
                if 'temp' in locals() and temp is not None: log_sensor_history(temp, humi); last_history_log = current_time
            time.sleep(0.1)
    except KeyboardInterrupt: print("\nCtrl+C detected. Shutting down.")
    finally:
        print("Releasing camera and cleaning up resources...")
        camera.release(); buzzer.write(0); fan_relay.write(0); lock_relay.write(0)
        client.loop_stop(); setText_norefresh(""); print("Cleanup complete.")

if __name__ == '__main__': main()
