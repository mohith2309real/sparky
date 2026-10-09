// Button: press a push button on pin 2 to light the LED on the board.
// Wire one side of the button to pin 2 and the other side to GND.

int button = 2;

void setup() {
  pinMode(button, INPUT_PULLUP);   // the pin reads HIGH until the button pulls it to GND
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(9600);
}

void loop() {
  if (digitalRead(button) == LOW) {     // pressed
    digitalWrite(LED_BUILTIN, HIGH);
    Serial.println("Pressed!");
  } else {
    digitalWrite(LED_BUILTIN, LOW);
  }
  delay(20);
}
