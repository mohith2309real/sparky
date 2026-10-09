// Fade: an LED on pin 9 slowly glows brighter and dimmer.
// Pin 9 has a ~ next to it, so it can fade (that's called PWM).

int led = 9;

void setup() {
  pinMode(led, OUTPUT);
}

void loop() {
  for (int brightness = 0; brightness <= 255; brightness += 5) {
    analogWrite(led, brightness);
    delay(30);
  }
  for (int brightness = 255; brightness >= 0; brightness -= 5) {
    analogWrite(led, brightness);
    delay(30);
  }
}
