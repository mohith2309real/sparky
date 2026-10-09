// Buzzer song: a piezo buzzer on pin 8 (other leg to GND) plays a little tune.

int buzzer = 8;
int notes[] = {262, 294, 330, 349, 392, 392, 440, 392, 349, 330, 294, 262};
int lengths[] = {250, 250, 250, 250, 500, 500, 250, 250, 250, 250, 250, 500};

void setup() {
  for (int i = 0; i < 12; i++) {
    tone(buzzer, notes[i], lengths[i]);
    delay(lengths[i] + 40);
  }
}

void loop() {
}
