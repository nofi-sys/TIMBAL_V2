#include <ArduinoJson.h>

const uint8_t NUM_SENSORS = 5;
const uint8_t SENSOR_PINS[NUM_SENSORS] = {A0, A1, A2, A3, A4};

const unsigned long PRESENCE_INTERVAL_MS = 250;
const size_t SERIAL_LINE_CAPACITY = 160;

struct RuntimeConfig {
  uint16_t minHitThreshold = 24;
  uint16_t quietTrackingLimit = 28;
  uint16_t presenceNoiseMax = 16;
  uint16_t recentHitKeepConnectedMs = 900;
  uint16_t refractoryMs = 38;
};

RuntimeConfig runtimeConfig;

struct SensorState {
  uint16_t baseline = 0;
  uint16_t noise = 0;
  uint16_t peak = 0;
  uint16_t lastValue = 0;
  bool initialized = false;
  bool connected = false;
  bool reportedConnected = false;
  unsigned long lastHitMs = 0;
  unsigned long lastReportMs = 0;
};

SensorState sensors[NUM_SENSORS];
char serialLine[SERIAL_LINE_CAPACITY];
size_t serialLineLen = 0;

static uint16_t absDiff(uint16_t a, uint16_t b) {
  return (a > b) ? (a - b) : (b - a);
}

static void sendHit(uint8_t ch, uint8_t vel) {
  StaticJsonDocument<96> doc;
  JsonObject hit = doc.createNestedObject("HIT");
  hit["ch"] = ch;
  hit["vel"] = vel;
  serializeJson(doc, Serial);
  Serial.println();
}

static void sendPadState(uint8_t ch, const SensorState& state) {
  StaticJsonDocument<128> doc;
  JsonObject pad = doc.createNestedObject("PADSTATE");
  pad["ch"] = ch;
  pad["conn"] = state.connected ? 1 : 0;
  pad["noise"] = state.noise;
  pad["value"] = state.lastValue;
  pad["peak"] = state.peak;
  serializeJson(doc, Serial);
  Serial.println();
}

static void sendConfigState() {
  StaticJsonDocument<160> doc;
  JsonObject cfg = doc.createNestedObject("CFGSTATE");
  cfg["min_hit"] = runtimeConfig.minHitThreshold;
  cfg["quiet"] = runtimeConfig.quietTrackingLimit;
  cfg["presence_noise"] = runtimeConfig.presenceNoiseMax;
  cfg["refractory"] = runtimeConfig.refractoryMs;
  cfg["keep_connected"] = runtimeConfig.recentHitKeepConnectedMs;
  serializeJson(doc, Serial);
  Serial.println();
}

static uint16_t clampU16(long value, uint16_t minValue, uint16_t maxValue) {
  if (value < static_cast<long>(minValue)) {
    return minValue;
  }
  if (value > static_cast<long>(maxValue)) {
    return maxValue;
  }
  return static_cast<uint16_t>(value);
}

static void applyConfigJson(JsonObject cfg) {
  if (cfg.containsKey("min_hit")) {
    runtimeConfig.minHitThreshold = clampU16(cfg["min_hit"].as<long>(), 8, 120);
  }
  if (cfg.containsKey("quiet")) {
    runtimeConfig.quietTrackingLimit = clampU16(cfg["quiet"].as<long>(), 4, 96);
  }
  if (cfg.containsKey("presence_noise")) {
    runtimeConfig.presenceNoiseMax = clampU16(cfg["presence_noise"].as<long>(), 2, 96);
  }
  if (cfg.containsKey("refractory")) {
    runtimeConfig.refractoryMs = clampU16(cfg["refractory"].as<long>(), 10, 140);
  }
  if (cfg.containsKey("keep_connected")) {
    runtimeConfig.recentHitKeepConnectedMs = clampU16(cfg["keep_connected"].as<long>(), 100, 2500);
  }
  sendConfigState();
}

static void processSerialLine(const char* line) {
  StaticJsonDocument<192> doc;
  DeserializationError err = deserializeJson(doc, line);
  if (err) {
    return;
  }

  if (doc["CFG"].is<JsonObject>()) {
    applyConfigJson(doc["CFG"].as<JsonObject>());
    return;
  }

  const char* req = doc["REQ"];
  if (req && strcmp(req, "CFG") == 0) {
    sendConfigState();
  }
}

static void pollSerialCommands() {
  while (Serial.available() > 0) {
    char c = static_cast<char>(Serial.read());
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      if (serialLineLen > 0) {
        serialLine[serialLineLen] = '\0';
        processSerialLine(serialLine);
        serialLineLen = 0;
      }
      continue;
    }
    if (serialLineLen + 1 < SERIAL_LINE_CAPACITY) {
      serialLine[serialLineLen++] = c;
    } else {
      serialLineLen = 0;
    }
  }
}

static void seedSensorState(uint8_t ch) {
  uint32_t acc = 0;
  for (uint8_t i = 0; i < 24; ++i) {
    acc += analogRead(SENSOR_PINS[ch]);
    delay(2);
  }
  sensors[ch].baseline = acc / 24;
  sensors[ch].noise = 0;
  sensors[ch].peak = 0;
  sensors[ch].lastValue = sensors[ch].baseline;
  sensors[ch].initialized = true;
  sensors[ch].connected = false;
  sensors[ch].reportedConnected = false;
  sensors[ch].lastHitMs = 0;
  sensors[ch].lastReportMs = 0;
}

static void updateSensor(uint8_t ch) {
  SensorState& state = sensors[ch];
  const unsigned long now = millis();
  const uint16_t value = analogRead(SENSOR_PINS[ch]);
  const uint16_t deviation = absDiff(value, state.baseline);

  state.lastValue = value;
  if (state.peak > 0) {
    state.peak -= 1;
  }
  if (deviation > state.peak) {
    state.peak = deviation;
  }

  const bool quietSample = deviation <= runtimeConfig.quietTrackingLimit;
  if (quietSample) {
    state.baseline = static_cast<uint16_t>(
      (static_cast<uint32_t>(state.baseline) * 15UL + value) / 16UL
    );
    state.noise = static_cast<uint16_t>(
      (static_cast<uint32_t>(state.noise) * 7UL + deviation) / 8UL
    );
  } else if (state.noise < deviation) {
    state.noise += 1;
  }

  state.connected = (
    state.noise <= runtimeConfig.presenceNoiseMax ||
    (now - state.lastHitMs) <= runtimeConfig.recentHitKeepConnectedMs
  );

  uint16_t dynamicThreshold = static_cast<uint16_t>(state.noise * 6U + 10U);
  if (dynamicThreshold < runtimeConfig.minHitThreshold) {
    dynamicThreshold = runtimeConfig.minHitThreshold;
  }

  if (
    state.connected &&
    deviation >= dynamicThreshold &&
    (now - state.lastHitMs) >= runtimeConfig.refractoryMs
  ) {
    state.lastHitMs = now;
    uint16_t clamped = deviation;
    if (clamped > 420) {
      clamped = 420;
    }
    const uint8_t velocity = static_cast<uint8_t>(
      map(clamped, dynamicThreshold, 420, 18, 127)
    );
    sendHit(ch, velocity);
  }

  const bool reportDue = (now - state.lastReportMs) >= PRESENCE_INTERVAL_MS;
  const bool stateChanged = state.connected != state.reportedConnected;
  if (reportDue || stateChanged) {
    sendPadState(ch, state);
    state.lastReportMs = now;
    state.reportedConnected = state.connected;
  }
}

void setup() {
  Serial.begin(115200);
  while (!Serial && millis() < 1500) {
    delay(1);
  }

  for (uint8_t ch = 0; ch < NUM_SENSORS; ++ch) {
    pinMode(SENSOR_PINS[ch], INPUT);
    seedSensorState(ch);
  }
  sendConfigState();
}

void loop() {
  pollSerialCommands();
  for (uint8_t ch = 0; ch < NUM_SENSORS; ++ch) {
    updateSensor(ch);
  }
}
