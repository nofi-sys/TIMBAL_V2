/*
  Multichannel raw analog streaming experiment for Arduino Leonardo / Micro.

  Use this when testing several piezo nodes before summing them in parallel.
  It keeps the same 8-byte binary packet used by HOST_ANALOG_STREAM_EXPERIMENT:
  - byte 0:  0xA1
  - byte 1:  channel index
  - byte 2-5: micros() timestamp
  - byte 6-7: analog value (0..1023)

  Channels match the runtime firmware inputs: A0..A4.
*/

const uint8_t FRAME_HEADER = 0xA1;
const uint8_t NUM_CHANNELS = 5;
const uint8_t SENSOR_PINS[NUM_CHANNELS] = {A0, A1, A2, A3, A4};

// One discarded read gives the ADC mux time to settle between high-impedance piezo channels.
const uint8_t DISCARD_READS_AFTER_CHANNEL_SWITCH = 1;

struct __attribute__((packed)) AnalogFrame {
  uint8_t header;
  uint8_t channel;
  uint32_t deviceMicros;
  uint16_t value;
};

uint16_t readSettledAnalog(uint8_t pin) {
  for (uint8_t i = 0; i < DISCARD_READS_AFTER_CHANNEL_SWITCH; ++i) {
    analogRead(pin);
  }
  return analogRead(pin);
}

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
    frame.value = readSettledAnalog(SENSOR_PINS[ch]);
    frame.deviceMicros = micros();
    Serial.write(reinterpret_cast<const uint8_t*>(&frame), sizeof(frame));
  }
}
