# README: Smart Server Room Monitor IoT System (Complete Final Guide)

This document provides a complete, step-by-step guide to building, configuring, and deploying the Smart Server Room Monitoring system. The system uses an ESP32 as a dedicated door sensor and a Raspberry Pi 5 as a central gateway for processing, alerts, evidence capture, and cloud integration.

**System Features:**
*   **Real-time Environmental Monitoring:** Tracks temperature and humidity with a Grove DHT11 sensor.
*   **Automated Climate Control:** Activates a cooling fan via a relay when a temperature threshold is exceeded.
*   **Remote Door Sensing:** An independent ESP32 node monitors a magnetic reed switch and reports the door's status (OPEN/CLOSED) instantly over the network.
*   **Visual Evidence Capture:** A USB webcam automatically captures a timestamped image upon a door-open event.
*   **Self-Hosted Image Server:** A Flask-based server on the Raspberry Pi makes captured images available on the local network without requiring paid cloud storage.
*   **Centralized Gateway Logic:** A Raspberry Pi 5 acts as the system's brain, processing events, triggering local alarms, controlling the lock, and managing all cloud communication.
*   **Cloud Integration:** All status updates, historical sensor data, and security events (with image filenames) are logged to a Google Firebase Realtime Database.
*   **Web-Based User Interface:** A Streamlit dashboard, run on any computer on the local network, provides real-time data visualization, historical trend graphs, security image display, and remote control of the door lock.
*   **Robust Deployment:** All Raspberry Pi software runs as auto-starting, self-recovering system services for maximum reliability.

## Table of Contents
1.  [System Architecture Overview](#1-system-architecture-overview)
2.  [Hardware Bill of Materials (BOM)](#2-hardware-bill-of-materials-bom)
3.  [Part 1: Cloud Backend Setup (Firebase)](#3-part-1-cloud-backend-setup-firebase)
4.  [Part 2: Raspberry Pi Gateway Setup](#4-part-2-raspberry-pi-gateway-setup)
    *   [4.1 RPi Hardware Assembly & Wiring](#41-rpi-hardware-assembly--wiring)
    *   [4.2 RPi OS & Software Installation](#42-rpi-os--software-installation)
    *   [4.3 RPi Code (Gateway & Image Server)](#43-rpi-code-gateway--image-server)
    *   [4.4 RPi Deployment as System Services](#44-rpi-deployment-as-system-services)
5.  [Part 3: ESP32 Sentry Node Setup](#5-part-3-esp32-sentry-node-setup)
    *   [5.1 ESP32 Hardware Assembly & Wiring](#51-esp32-hardware-assembly--wiring)
    *   [5.2 ESP32 Arduino IDE Setup](#52-esp32-arduino-ide-setup)
    *   [5.3 ESP32 Firmware Code (Final)](#53-esp32-firmware-code-final)
6.  [Part 4: User Interface Setup (Streamlit Dashboard)](#6-part-4-user-interface-setup-streamlit-dashboard)
7.  [Final System Operation & Verification](#7-final-system-operation--verification)

---

## 1. System Architecture Overview
The system is composed of four decoupled components communicating over the local network and the internet.

*   **ESP32 Sentry Node:** Monitors the door. Publishes status changes to the MQTT broker.
*   **Raspberry Pi Gateway:** Runs the MQTT broker. Subscribes to ESP32 messages. Controls local hardware (alarm, lock, fan). Reads local sensors (DHT). Captures images from the webcam. Publishes all data to Firebase. Runs a Flask server to provide images to the UI.
*   **Firebase Cloud Backend:** The central database for all status, event, and historical data.
*   **Streamlit UI:** Reads data directly from Firebase for display. Fetches images from the RPi's Flask server. Publishes control commands (e.g., "UNLOCK") to the MQTT broker on the Raspberry Pi.

## 2. Hardware Bill of Materials (BOM)

| Qty | Component                       | Role                               |
|:---:|---------------------------------|------------------------------------|
| 1   | Raspberry Pi 5                  | Gateway Controller                 |
| 1   | Grove Base Hat for Raspberry Pi | RPi Peripheral Interface           |
| 1   | Logitech C270 USB Webcam        | Visual Evidence Capture            |
| 1   | ESP32-WROOM-32 Dev Kit          | Sentry Node Controller             |
| 1   | Grove DHT11 Sensor              | Temperature & Humidity             |
| 1   | Grove 16x2 LCD                  | Local Status Display               |
| 1   | Grove Buzzer                    | Audible Alarm                      |
| 2   | Grove Relay                     | Fan & Lock Actuation               |
| 1   | Magnetic Reed Switch            | Door Sensor                        |
| 1   | 🟢 Green LED, 🔴 Red LED        | ESP32 Status Indicators            |
| 1   | Breadboard & Jumper Wires       | Prototyping                        |
| 1   | 10kΩ Resistor (Brown-Black-Orange) | Reed Switch Pull-up                |
| 2   | 1kΩ Resistors (Brown-Black-Red) | LED Current Limiting               |
| 1   | 5V DC Fan & 6V Solenoid Lock    | Actuators                          |
| 1   | 1N4001 Flyback Diode            | **MANDATORY** for Solenoid         |
| -   | Power Supplies (USB-C for RPi, Micro-USB for ESP32, 6V Adapter for Lock) | Power                             |

## 3. Part 1: Cloud Backend Setup (Firebase)
1.  Go to the [Firebase Console](https://console.firebase.google.com/) and create a new project.
2.  In the project dashboard, go to **Build -> Realtime Database**. Click "Create Database".
3.  Go to the **Rules** tab. Delete the existing text and replace it with the following, then click **Publish**.
    ```json
    {
      "rules": {
        ".read": "true",
        ".write": "true"
      }
    }
    ```

## 4. Part 2: Raspberry Pi Gateway Setup

### 4.1 RPi Hardware Assembly & Wiring
1.  Attach the **Grove Base Hat** to the Raspberry Pi 5.
2.  Connect the **USB Webcam** to any blue USB 3.0 port.
3.  **Grove Connections:**
    *   Grove 16x2 LCD -> **I2C** Port
    *   Grove DHT Sensor -> **D22** Port
    *   Grove Buzzer -> **D5** Port
    *   Fan Relay -> **D16** Port
    *   Lock Relay -> **D18** Port
4.  **Fan Relay Wiring (D16):**
    *   RPi **5V Pin** -> Relay `COM` terminal.
    *   Relay `NO` terminal -> Fan `Red (+)` wire.
    *   Fan `Black (-)` wire -> RPi **GND Pin**.
5.  **Lock Relay Wiring (D18):**
    *   **6V** Adapter `(+)` wire -> Relay `COM` terminal.
    *   Relay `NO` terminal -> Solenoid `Red (+)` wire.
    *   Solenoid `Black (-)` wire -> **6V** Adapter `(-)` wire.
    *   **Flyback Diode:** Connect across the Solenoid terminals. **Silver stripe on diode to Solenoid's Red (+)**.

### 4.2 RPi OS & Software Installation
1.  Flash and boot **Raspberry Pi OS (64-bit)**.
2.  Open a Terminal and install system dependencies:
    ```bash
    sudo apt update && sudo apt upgrade -y
    sudo apt install mosquitto mosquitto-clients python3-opencv -y
    ```
3.  Install required Grove and Python libraries:
    ```bash
    curl -sL https://github.com/Seeed-Studio/grove.py/raw/master/install.sh | sudo bash -s -
    pip install paho-mqtt pyrebase4 seeed-python-dht Flask
    ```
4.  Create the directory for captured images:
    ```bash
    mkdir /home/pi/captures
    ```

### 4.3 RPi Code (Gateway & Image Server)

#### Main Gateway Script
Create a file at `/home/pi/final_gateway.py` and paste the following complete code:
```python
# FILE: /home/pi/final_gateway.py (FINAL VERSION with Camera Fix)
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
```

#### Image Server Script
Create a file at `/home/pi/image_server.py` and paste the following code:
```python
# FILE: /home/pi/image_server.py
from flask import Flask, send_from_directory
import os

IMAGE_DIR = os.path.join(os.path.expanduser('~'), 'captures')
app = Flask(__name__)

@app.route('/captures/<path:filename>')
def serve_image(filename):
    return send_from_directory(IMAGE_DIR, filename)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)
```

### 4.4 RPi Deployment as System Services
1.  **Create the Main Gateway Service File:**
    ```bash
    sudo nano /etc/systemd/system/server-monitor.service
    ```
2.  **Paste the following configuration:**
    ```ini
    [Unit]
    Description=Smart Server Room Monitor Gateway
    After=network-online.target

    [Service]
    ExecStart=/usr/bin/python3 /home/pi/final_gateway.py
    WorkingDirectory=/home/pi
    Restart=always
    User=pi

    [Install]
    WantedBy=multi-user.target
    ```
3.  **Create the Image Server Service File:**
    ```bash
    sudo nano /etc/systemd/system/image-server.service
    ```
4.  **Paste the following configuration:**
    ```ini
    [Unit]
    Description=Flask Image Server for Server Monitor
    After=network-online.target

    [Service]
    ExecStart=/usr/bin/python3 /home/pi/image_server.py
    WorkingDirectory=/home/pi
    Restart=always
    User=pi

    [Install]
    WantedBy=multi-user.target
    ```
5.  **Enable and Start Both Services:**
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable server-monitor.service
    sudo systemctl start server-monitor.service
    sudo systemctl enable image-server.service
    sudo systemctl start image-server.service
    ```

## 5. Part 3: ESP32 Sentry Node Setup

### 5.1 ESP32 Hardware Assembly & Wiring
1.  Place ESP32 on breadboard. `ESP32 3V3` to `+` rail, `ESP32 GND` to `-` rail.
2.  **Reed Switch (Pin 15):** One wire to `GPIO 15`, other to `-` rail. 10kΩ Resistor between `GPIO 15` and `+` rail.
3.  **Green LED (Pin 23):** `GPIO 23` -> 1kΩ Resistor -> LED Anode (+). LED Cathode (-) -> `-` rail.
4.  **Red LED (Pin 22):** `GPIO 22` -> 1kΩ Resistor -> LED Anode (+). LED Cathode (-) -> `-` rail.

### 5.2 ESP32 Arduino IDE Setup
1.  Install the ESP32 board manager.
2.  Install `PubSubClient` library by Nick O'Leary (`Tools > Manage Libraries...`).
3.  Select your ESP32 board and COM port.

### 5.3 ESP32 Firmware Code (Final)
Paste into Arduino IDE and upload. **Ensure `MQTT_BROKER_IP` is correct.**
```cpp
// FILE: esp32_sentry_firmware.ino
#include <WiFi.h>
#include <PubSubClient.h>

const int REED_SWITCH_PIN = 15; const int GREEN_LED_PIN = 23; const int RED_LED_PIN = 22;
const char* WIFI_SSID = "B100M-T8"; const char* WIFI_PASSWORD = "12345678";
const char* MQTT_BROKER_IP = "192.168.0.106"; // <<< YOUR RASPBERRY PI's IP
const int MQTT_PORT = 1883; const char* MQTT_DOOR_TOPIC = "server-room/01/status/door";

WiFiClient wifiClient; PubSubClient mqttClient(wifiClient); int lastDoorState = -1;

void setup_wifi() {
  Serial.print("Connecting to WiFi..."); WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.println("\nWiFi connected.");
}

void reconnect_mqtt() {
  while (!mqttClient.connected()) {
    Serial.print("Attempting MQTT...");
    if (mqttClient.connect("esp32-sentry")) Serial.println("connected.");
    else { Serial.print("failed, rc="); Serial.print(mqttClient.state()); delay(5000); }
  }
}

void setup() {
  Serial.begin(115200); pinMode(REED_SWITCH_PIN, INPUT_PULLUP);
  pinMode(GREEN_LED_PIN, OUTPUT); pinMode(RED_LED_PIN, OUTPUT);
  setup_wifi(); mqttClient.setServer(MQTT_BROKER_IP, MQTT_PORT);
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) setup_wifi();
  if (!mqttClient.connected()) reconnect_mqtt();
  mqttClient.loop();
  int currentDoorState = digitalRead(REED_SWITCH_PIN);
  if (currentDoorState != lastDoorState) {
    if (currentDoorState == HIGH) { // OPEN
      digitalWrite(GREEN_LED_PIN, LOW); digitalWrite(RED_LED_PIN, HIGH);
      mqttClient.publish(MQTT_DOOR_TOPIC, "OPEN");
    } else { // CLOSED
      digitalWrite(GREEN_LED_PIN, HIGH); digitalWrite(RED_LED_PIN, LOW);
      mqttClient.publish(MQTT_DOOR_TOPIC, "CLOSED");
    }
    lastDoorState = currentDoorState;
  }
  delay(100);
}
```

## 6. Part 4: User Interface Setup (Streamlit Dashboard)
Run this on a laptop on the same network.
1.  **Install Dependencies:** `pip install streamlit paho-mqtt pyrebase4 pandas`
2.  **Create `dashboard.py`** and paste the following. **Ensure `RPI_IP_ADDRESS` is correct.**
    ```python
    # FILE: dashboard.py (FINAL VERSION with Camera Display)
    import streamlit as st
    import pyrebase
    import paho.mqtt.client as mqtt
    import pandas as pd
    from datetime import datetime

    # --- CONFIGURATION ---
    FIREBASE_CONFIG = {
        "apiKey": "AIzaSyBn2HqgrwqL7hMXI3cd7jB0HvdELCT3xSw",
        "authDomain": "iot-school-e8b0b.firebaseapp.com",
        "databaseURL": "https://iot-school-e8b0b-default-rtdb.asia-southeast1.firebasedatabase.app",
        "storageBucket": "iot-school-e8b0b.appspot.com"
    }
    RPI_IP_ADDRESS = "192.168.0.106" # <<< YOUR RASPBERRY PI's IP
    MQTT_BROKER_IP = RPI_IP_ADDRESS
    IMAGE_SERVER_URL = f"http://{RPI_IP_ADDRESS}:8000/captures"
    MQTT_COMMAND_TOPIC = "server-room/01/commands/lock"

    st.set_page_config(page_title="Server Room Monitor", layout="wide", initial_sidebar_state="collapsed")

    @st.cache_resource
    def init_firebase(): return pyrebase.initialize_app(FIREBASE_CONFIG)
    firebase = init_firebase(); db = firebase.database()

    def get_mqtt_client():
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, "streamlit-ui")
        try: client.connect(MQTT_BROKER_IP, 1883, 60); return client
        except Exception: st.error(f"MQTT Broker at {MQTT_BROKER_IP} unreachable.", icon="📡"); return None

    @st.cache_data(ttl=5)
    def fetch_data(): return db.child("system_status").get().val(), db.child("event_logs").get().val(), db.child("sensor_history").get().val()
    
    st.title("🔒 Smart Server Room Monitor")
    status_data, log_data, history_data = fetch_data()

    if status_data:
        st.caption(f"Last update: {datetime.fromtimestamp(status_data.get('timestamp', 0)).strftime('%H:%M:%S')}")
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("🌡️ Temperature", f"{status_data.get('temperature', 'N/A')} °C")
        kpi2.metric("💧 Humidity", f"{status_data.get('humidity', 'N/A')} %")
        fan_on = status_data.get("fan_on", False)
        kpi3.metric("💨 Cooling Fan", "ACTIVE" if fan_on else "OFF", delta="Overheating!" if fan_on else "Nominal", delta_color="inverse" if fan_on else "normal")
    else: st.warning("Awaiting first status update...")

    tab1, tab2, tab3 = st.tabs(["🕹️ Controls & Live Events", "📈 Environmental Trends", "🖼️ Security Camera"])
    with tab1:
        st.header("Remote Controls & Event Log")
        if st.button("🔓 UNLOCK DOOR FOR 2 SECONDS", use_container_width=True, type="primary"):
            client = get_mqtt_client();
            if client: client.publish(MQTT_COMMAND_TOPIC, "UNLOCK"); client.disconnect(); st.success("Unlock command sent!", icon="✅")
        st.subheader("📜 Event Log")
        if log_data:
            logs = sorted(log_data.values(), key=lambda x: x['timestamp'], reverse=True)
            display_logs = [{"Time": datetime.fromtimestamp(l['timestamp']).strftime('%Y-%m-%d %H:%M:%S'), "Level": l['level'], "Message": l['message']} for l in logs]
            st.dataframe(pd.DataFrame(display_logs), use_container_width=True, hide_index=True)
        else: st.info("No event logs recorded.")
    with tab2:
        st.header("📈 Environmental Trends (Last 24h)")
        if history_data:
            df = pd.DataFrame.from_dict(history_data, orient='index'); df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
            st.line_chart(df.set_index('timestamp').sort_index().last('24h')[['temperature', 'humidity']])
        else: st.info("No historical data yet.")
    with tab3:
        st.header("🖼️ Latest Security Camera Capture")
        if log_data:
            latest_image_log = next((log for log in sorted(log_data.values(), key=lambda x: x['timestamp'], reverse=True) if 'imageFile' in log), None)
            if latest_image_log:
                st.image(f"{IMAGE_SERVER_URL}/{latest_image_log['imageFile']}", caption=f"Evidence from event at: {datetime.fromtimestamp(latest_image_log['timestamp']).strftime('%H:%M:%S')}", use_column_width=True)
            else: st.info("No security images have been captured yet.")
        else: st.info("No event logs available.")
    
    st.divider();
    if st.button("Force Refresh"): st.cache_data.clear(); st.rerun()
    ```

## 7. Final System Operation & Verification
1.  **Power On:** Provide power to the Raspberry Pi, ESP32 (via a USB charger), and the 6V adapter.
2.  **Wait:** Allow 1-2 minutes for the RPi to boot and its services to start, and for the ESP32 to connect.
3.  **Launch UI:** On your laptop, open a terminal and run: `streamlit run dashboard.py`.
4.  **Verify:** Open the URL in a browser. You should see live data. Test the system by triggering the reed switch with a magnet and using the "UNLOCK" button on the dashboard. An image should appear in the Security Camera tab after a door-open event.
5.  **Reboot Test:**
    *   Reboot the Raspberry Pi with `sudo reboot`.
    *   After it comes back online, verify that the dashboard starts receiving fresh data automatically, confirming the deployment was successful.
