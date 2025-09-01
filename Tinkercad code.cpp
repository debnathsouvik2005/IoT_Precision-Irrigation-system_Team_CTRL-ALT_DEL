#include <Servo.h>
#include <LiquidCrystal.h>

// Pin definitions
#define SOIL_SENSOR_1 A0
#define SOIL_SENSOR_2 A1
#define SOIL_SENSOR_3 A2
#define SOIL_SENSOR_4 A3
#define SOIL_SENSOR_5 A4
#define TEMP_SENSOR A5

#define LED_LOW 13      // Red - Low moisture
#define LED_OPTIMAL 12  // Green - Optimal moisture  
#define LED_HIGH 11     // Blue - High moisture

#define SERVO_PIN 9

// Objects
Servo valveServo;
LiquidCrystal lcd(2, 3, 4, 5, 6, 7);

// Variables
int soilValues[5];
float avgMoisture = 0;
float temperature = 0;
int moistureThresholdLow = 30;
int moistureThresholdHigh = 70;
bool irrigationActive = false;

void setup() {
  Serial.begin(9600);
  
  // Initialize LCD
  lcd.begin(16, 2);
  lcd.print("IoT Irrigation");
  lcd.setCursor(0, 1);
  lcd.print("Initializing...");
  
  // Initialize LEDs
  pinMode(LED_LOW, OUTPUT);
  pinMode(LED_OPTIMAL, OUTPUT);
  pinMode(LED_HIGH, OUTPUT);
  
  // Initialize servo
  valveServo.attach(SERVO_PIN);
  valveServo.write(0); // Valve closed initially
  
  delay(2000);
  Serial.println("IoT Irrigation System Started");
}

void loop() {
  // Read all soil moisture sensors
  readSoilSensors();
  
  // Read temperature
  readTemperature();
  
  // Calculate average moisture
  calculateAverageMoisture();
  
  // Display readings
  displayReadings();
  
  // Check irrigation needs
  checkIrrigationNeeds();
  
  // Update status LEDs
  updateStatusLEDs();
  
  delay(2000); // Update every 2 seconds for simulation
}



void readSoilSensors() {
  soilValues[0] = analogRead(SOIL_SENSOR_1);
  soilValues[1] = analogRead(SOIL_SENSOR_2);
  soilValues[2] = analogRead(SOIL_SENSOR_3);
  soilValues[3] = analogRead(SOIL_SENSOR_4);
  soilValues[4] = analogRead(SOIL_SENSOR_5);
  for (int i = 0; i < 5; i++) {
    soilValues[i] = map(soilValues[i], 0, 1023, 100, 0);
    soilValues[i] = constrain(soilValues[i], 0, 100);
  }
}


void readTemperature() {
  int tempReading = analogRead(TEMP_SENSOR);
  float voltage = (tempReading * 5.0) / 1024.0;
  temperature = (voltage - 0.5) * 100; // TMP36 conversion
}

void calculateAverageMoisture() {
  int total = 0;
  for (int i = 0; i < 5; i++) {
    total += soilValues[i];
  }
  avgMoisture = total / 5.0;
}

void displayReadings() {
  // LCD Display
  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("Moisture: ");
  lcd.print(avgMoisture, 1);
  lcd.print("%");
  
  lcd.setCursor(0, 1);
  lcd.print("Temp: ");
  lcd.print(temperature, 1);
  lcd.print("C");
  
  if (irrigationActive) {
    lcd.print(" IRR");
  }
  
  // Serial Monitor Output
  Serial.println("=== Sensor Readings ===");
  Serial.print("Soil Sensors: ");
  for (int i = 0; i < 5; i++) {
    Serial.print("S");
    Serial.print(i + 1);
    Serial.print(":");
    Serial.print(soilValues[i]);
    Serial.print("% ");
  }
  Serial.println();
  
  Serial.print("Average Moisture: ");
  Serial.print(avgMoisture);
  Serial.println("%");
  
  Serial.print("Temperature: ");
  Serial.print(temperature);
  Serial.println("°C");
  
  Serial.print("Irrigation Status: ");
  Serial.println(irrigationActive ? "ACTIVE" : "INACTIVE");
  Serial.println("========================");
}

void checkIrrigationNeeds() {
  if (avgMoisture < moistureThresholdLow && !irrigationActive) {
    // Start irrigation
    startIrrigation();
    Serial.println(">> Starting irrigation - Low soil moisture detected");
  } 
  else if (avgMoisture > moistureThresholdHigh && irrigationActive) {
    // Stop irrigation
    stopIrrigation();
    Serial.println(">> Stopping irrigation - Adequate soil moisture");
  }
  
  // Emergency high temperature irrigation
  if (temperature > 35 && avgMoisture < 50 && !irrigationActive) {
    startIrrigation();
    Serial.println(">> Emergency irrigation - High temperature detected");
  }
}

void startIrrigation() {
  irrigationActive = true;
  valveServo.write(90); // Open valve (90 degrees)
  Serial.println("IRRIGATION STARTED");
}

void stopIrrigation() {
  irrigationActive = false;
  valveServo.write(0); // Close valve (0 degrees)
  Serial.println("IRRIGATION STOPPED");
}

void updateStatusLEDs() {
  // Turn off all LEDs first
  digitalWrite(LED_LOW, LOW);
  digitalWrite(LED_OPTIMAL, LOW);
  digitalWrite(LED_HIGH, LOW);
  
  // Light appropriate LED based on moisture level
  if (avgMoisture < moistureThresholdLow) {
    digitalWrite(LED_LOW, HIGH); // Red LED - Low moisture
  }
  else if (avgMoisture > moistureThresholdHigh) {
    digitalWrite(LED_HIGH, HIGH); // Blue LED - High moisture
  }
  else {
    digitalWrite(LED_OPTIMAL, HIGH); // Green LED - Optimal moisture
  }
}