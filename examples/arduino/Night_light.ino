// Night light: a light sensor (photoresistor) on A0 turns the LED on when it gets dark.
// Photoresistor between 5V and A0, and a 10k resistor between A0 and GND.

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  int light = analogRead(A0);       // 0 (dark) to 1023 (bright)
  Serial.print("light:");
  Serial.println(light);
  if (light < 300) {
    digitalWrite(LED_BUILTIN, HIGH);
  } else {
    digitalWrite(LED_BUILTIN, LOW);
  }
  delay(100);
}
