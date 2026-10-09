// Serial hello: the board talks to the computer.
// Upload, then open the Serial Monitor at 9600 baud. Type your name and press Enter!

void setup() {
  Serial.begin(9600);
  Serial.println("Hi! I'm your Arduino. What's your name?");
}

void loop() {
  if (Serial.available()) {
    String name = Serial.readStringUntil('\n');
    name.trim();
    Serial.println("Nice to meet you, " + name + "!");
  }
}
