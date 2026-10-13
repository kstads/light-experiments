#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_OPT4048.h>
#include <Adafruit_NeoPixel.h>

// Use a dedicated Home Assistant/MQTT user here. Do not commit real passwords.
constexpr char WIFI_SSID[] = "REPLACE_WITH_WIFI_NAME";
constexpr char WIFI_PASSWORD[] = "REPLACE_WITH_WIFI_PASSWORD";
constexpr char MQTT_HOST[] = "REPLACE_WITH_MQTT_BROKER_HOST";
constexpr uint16_t MQTT_PORT = 1883;
constexpr char MQTT_USER[] = "REPLACE_WITH_MQTT_USER";
constexpr char MQTT_PASSWORD[] = "REPLACE_WITH_MQTT_PASSWORD";

constexpr char COMMAND_TOPIC[] = "lighting/calibrator/measure";
constexpr char RESULT_TOPIC[] = "lighting/calibrator/measurement";
constexpr char STATUS_TOPIC[] = "lighting/calibrator/status";
constexpr uint8_t SAMPLE_COUNT = 20;
constexpr uint32_t SAMPLE_SPACING_MS = 125;

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
Adafruit_OPT4048 opt4048;
Adafruit_NeoPixel onboardPixel(1, PIN_NEOPIXEL, NEO_GRB + NEO_KHZ800);

void disableOnboardLeds() {
  // GPIO 20 must remain HIGH because it powers both the NeoPixel and the
  // STEMMA QT connector. Turn the pixel black instead of cutting its power.
  pinMode(NEOPIXEL_I2C_POWER, OUTPUT);
  digitalWrite(NEOPIXEL_I2C_POWER, HIGH);

  onboardPixel.begin();
  onboardPixel.clear();
  onboardPixel.show();

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
}

String jsonStringValue(const String &json, const char *key) {
  String marker = String('"') + key + "\":";
  int start = json.indexOf(marker);
  if (start < 0) return "";
  start += marker.length();
  while (start < (int)json.length() && json[start] == ' ') start++;
  if (start < (int)json.length() && json[start] == '"') {
    int end = json.indexOf('"', start + 1);
    return end < 0 ? "" : json.substring(start + 1, end);
  }
  int end = json.indexOf(',', start);
  if (end < 0) end = json.indexOf('}', start);
  return end < 0 ? "" : json.substring(start, end);
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) delay(250);
}

void connectMqtt() {
  while (!mqtt.connected()) {
    String clientId = "opt4048-calibrator-" + String((uint32_t)ESP.getEfuseMac(), HEX);
    if (mqtt.connect(clientId.c_str(), MQTT_USER, MQTT_PASSWORD,
                     STATUS_TOPIC, 1, true, "offline")) {
      mqtt.publish(STATUS_TOPIC, "online", true);
      mqtt.subscribe(COMMAND_TOPIC, 1);
    } else {
      delay(1000);
    }
  }
}

void measureAndPublish(const String &command) {
  const String requestId = jsonStringValue(command, "request_id");
  const String requestedKelvin = jsonStringValue(command, "kelvin");
  const String requestedBrightness = jsonStringValue(command, "brightness_pct");

  double sumX = 0, sumY = 0, sumLux = 0, sumCct = 0;
  double minLux = 1e30, maxLux = -1e30;
  uint8_t valid = 0;

  for (uint8_t i = 0; i < SAMPLE_COUNT; i++) {
    double x, y, lux;
    if (opt4048.getCIE(&x, &y, &lux)) {
      sumX += x;
      sumY += y;
      sumLux += lux;
      sumCct += opt4048.calculateColorTemperature(x, y);
      minLux = min(minLux, lux);
      maxLux = max(maxLux, lux);
      valid++;
    }
    delay(SAMPLE_SPACING_MS);
  }

  if (!valid) {
    mqtt.publish(STATUS_TOPIC, "measurement_error", true);
    return;
  }

  const double avgX = sumX / valid;
  const double avgY = sumY / valid;
  const double avgLux = sumLux / valid;
  const double avgCct = sumCct / valid;

  char payload[512];
  snprintf(payload, sizeof(payload),
           "{\"request_id\":\"%s\",\"requested_kelvin\":%s,"
           "\"requested_brightness_pct\":%s,\"cct\":%.2f,\"x\":%.8f,"
           "\"y\":%.8f,\"lux\":%.4f,\"foot_candles\":%.4f,"
           "\"lux_min\":%.4f,\"lux_max\":%.4f,\"samples\":%u}",
           requestId.c_str(), requestedKelvin.c_str(), requestedBrightness.c_str(),
           avgCct, avgX, avgY, avgLux, avgLux / 10.76391,
           minLux, maxLux, valid);

  mqtt.publish(RESULT_TOPIC, payload, false);
  mqtt.publish(STATUS_TOPIC, "online", true);

  // Paste directly into a spreadsheet or save the Serial Monitor output.
  Serial.printf("%s,%s,%.2f,%.8f,%.8f,%.4f,%.4f,%.4f,%u\n",
                requestedKelvin.c_str(), requestedBrightness.c_str(), avgCct,
                avgX, avgY, avgLux, minLux, maxLux, valid);
}

void onMqttMessage(char *topic, byte *payload, unsigned int length) {
  if (String(topic) != COMMAND_TOPIC) return;
  String command;
  command.reserve(length + 1);
  for (unsigned int i = 0; i < length; i++) command += (char)payload[i];
  measureAndPublish(command);
}

void setup() {
  Serial.begin(115200);
  delay(500);
  disableOnboardLeds();
  Wire.begin();

  if (!opt4048.begin()) {
    Serial.println("OPT4048 not found. Check the STEMMA QT cable.");
    while (true) delay(1000);
  }
  opt4048.setRange(OPT4048_RANGE_AUTO);
  opt4048.setConversionTime(OPT4048_CONVERSION_TIME_100MS);
  opt4048.setMode(OPT4048_MODE_CONTINUOUS);

  connectWiFi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setCallback(onMqttMessage);
  mqtt.setBufferSize(768);
  connectMqtt();

  Serial.println("requested_kelvin,requested_brightness_pct,measured_cct,x,y,lux,lux_min,lux_max,samples");
}

void loop() {
  connectWiFi();
  connectMqtt();
  mqtt.loop();
}
