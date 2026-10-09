// Traffic light: a red, a yellow and a green LED (each with a 220 ohm resistor)
// on pins 12, 11 and 10. Long legs to the pins, short legs to GND.

int red = 12;
int yellow = 11;
int green = 10;

void setup() {
  pinMode(red, OUTPUT);
  pinMode(yellow, OUTPUT);
  pinMode(green, OUTPUT);
}

void light(int pin, int seconds) {
  digitalWrite(pin, HIGH);
  delay(seconds * 1000);
  digitalWrite(pin, LOW);
}

void loop() {
  light(red, 3);
  light(green, 3);
  light(yellow, 1);
}
