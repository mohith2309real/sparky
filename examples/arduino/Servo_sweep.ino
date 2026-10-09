// Servo sweep: a servo motor on pin 9 swings from 0 to 180 degrees and back.
// Servo wires: brown/black to GND, red to 5V, orange/yellow to pin 9.

#include <Servo.h>

Servo arm;

void setup() {
  arm.attach(9);
}

void loop() {
  for (int angle = 0; angle <= 180; angle += 2) {
    arm.write(angle);
    delay(15);
  }
  for (int angle = 180; angle >= 0; angle -= 2) {
    arm.write(angle);
    delay(15);
  }
}
