/*
  Host-side analog streaming experiment for Arduino Leonardo / Micro.

  Purpose:
  - stream raw analog samples to the PC
  - let the desktop app detect hits on the host
  - compare sensitivity / estimated transport lag against firmware-side onset detection

  Binary packet format (8 bytes, little-endian):
  - byte 0:  0xA1
  - byte 1:  channel index
  - byte 2-5: micros() timestamp
  - byte 6-7: analog value (0..1023)
*/

const uint8_t FRAME_HEADER = 0xA1;
const uint8_t NUM_CHANNELS = 1;
const uint8_t SENSOR_PINS[NUM_CHANNELS] = {A0};

struct __attribute__((packed)) AnalogFrame {
  uint8_t header;
  uint8_t channel;
  uint32_t deviceMicros;
  uint16_t value;
};

void setup() {
  Serial.begin(2000000);
  while (!Serial && millis() < 1500) {
    delay(1);
  }
}

void loop() {
  for (uint8_t ch = 0; ch < NUM_CHANNELS; ++ch) {
    AnalogFrame frame;
    frame.header = FRAME_HEADER;
    frame.channel = ch;
    frame.deviceMicros = micros();
    frame.value = analogRead(SENSOR_PINS[ch]);
    Serial.write(reinterpret_cast<const uint8_t*>(&frame), sizeof(frame));
  }
}
