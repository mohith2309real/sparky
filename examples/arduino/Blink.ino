// Blink: the "hello world" of electronics.
// The little LED on the board turns on and off every half a second.

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);   // the LED is something we control
}

void loop() {
  digitalWrite(LED_BUILTIN, HIGH);   // on
  delay(500);                        // wait half a second (500 milliseconds)
  digitalWrite(LED_BUILTIN, LOW);    // off
  delay(500);
}
