void readMuteButtonsAndUpdateLatch(){
  for(uint8_t i=0;i<NUM_SENSORS;i++){
    bool pressed = (digitalRead(MUTE_PINS[i]) == LOW);
    if (pressed && !btnPrev[i]) {
      StaticJsonDocument<64> d;
      d["MUTE"]["ch"] = i;
      d["MUTE"]["state"] = 1;
      serializeJson(d, Serial); Serial.println();
      if (noteActive[i]) { midiNoteOff(MIDI_CH_OF[i], activeNote[i]); midiFlush(); noteActive[i]=false; envFollow[i]=false; envArmed[i]=false; }
      muteLatched[i] = true;
    }
    else if (!pressed && btnPrev[i]) {
      StaticJsonDocument<64> d2;
      d2["MUTE"]["ch"] = i;
      d2["MUTE"]["state"] = 0;
      serializeJson(d2, Serial); Serial.println();
      muteLatched[i] = false;
      exprTarget[i] = EXP_MAX;
    }
    else {
      muteLatched[i] = pressed;
    }
    btnPrev[i] = pressed;
    btnNow[i] = pressed;
  }
}
