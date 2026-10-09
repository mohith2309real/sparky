// Distance sensor: an HC-SR04 ultrasonic sensor measures how far away things are.
// VCC to 5V, GND to GND, TRIG to pin 7, ECHO to pin 6.
// Open the Serial Monitor (or the Plotter!) at 9600 baud to see the distance.

int trig = 7;
int echo = 6;

void setup() {
  pinMode(trig, OUTPUT);
  pinMode(echo, INPUT);
  Serial.begin(9600);
}

void loop() {
  digitalWrite(trig, LOW);
  delayMicroseconds(2);
  digitalWrite(trig, HIGH);         // a tiny "ping" of sound
  delayMicroseconds(10);
  digitalWrite(trig, LOW);
  long echoTime = pulseIn(echo, HIGH, 30000);   // how long until the echo comes back
  float cm = echoTime * 0.0343 / 2;             // sound travels 0.0343 cm per microsecond
  Serial.print("distance:");
  Serial.println(cm);
  delay(100);
}
