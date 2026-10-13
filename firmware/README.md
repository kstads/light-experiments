# ESP32 measurement firmware

The sketches are kept beside their experiment records:

- `calibration/koto-sd/legacy-color-capture/esp32_opt4048_calibrator.ino` — original Wi-Fi/MQTT color measurement sketch.
- `calibration/koto-sd/mqtt_fast_capture/mqtt_fast_capture.ino` — later fast MQTT capture sketch.
- `calibration/koto-sd/usb_fast_capture/usb_fast_capture.ino` — fast USB capture sketch.
- `calibration/koto-hc/firmware-source.ino` — HC run firmware source.

All use the ESP32 Arduino core and OPT4048 sensor; applicable sketches also use Adafruit NeoPixel. MQTT sketches use PubSubClient. The source collection records Adafruit OPT4048 library version 1.0.2 for one MQTT run; it does not record a complete pinned toolchain or library set for every sketch.

For MQTT sketches, provide a local `secrets.h` with Wi-Fi and MQTT settings. A safe `secrets.h.example` is included beside the SD MQTT sketch; copy it to `secrets.h` and fill in local values before building. The repository ignores `secrets.h`. The USB sketch does not need Wi-Fi or MQTT credentials.

The examples document source needed to reproduce acquisition. No sketch was flashed or run as part of this publication.
