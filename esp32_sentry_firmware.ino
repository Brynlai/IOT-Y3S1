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
