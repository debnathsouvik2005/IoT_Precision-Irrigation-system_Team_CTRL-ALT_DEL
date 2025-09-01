/*
 * IoT Precision Irrigation System
 * Advanced soil monitoring with ML prediction
 * Compatible with ESP32 and Arduino IDE
 */

#include <WiFi.h>
#include <WebServer.h>
#include <DHT.h>
#include <ArduinoJson.h>
#include <HTTPClient.h>
#include <EEPROM.h>
#include "time.h"

// Network Configuration
const char* ssid = "YOUR_WIFI_SSID";
const char* password = "YOUR_WIFI_PASSWORD";

// Sensor Pin Definitions
#define DHT_PIN 2
#define DHT_TYPE DHT22
#define RAIN_SENSOR 4
#define LIGHT_SENSOR 5
#define SOIL_SENSOR_1 34
#define SOIL_SENSOR_2 35
#define SOIL_SENSOR_3 32
#define SOIL_SENSOR_4 33
#define SOIL_SENSOR_5 36

// Relay Pin Definitions
#define RELAY_1 18  // Zone 1 Valve
#define RELAY_2 19  // Zone 2 Valve
#define RELAY_3 21  // Water Pump
#define RELAY_4 22  // Emergency Valve

// Sensor Objects and Variables
DHT dht(DHT_PIN, DHT_TYPE);
WebServer server(80);

// Sensor Data Structure
struct SensorData {
  float soilMoisture[35];
  float temperature;
  float humidity;
  int lightIntensity;
  bool isRaining;
  float batteryVoltage;
  unsigned long timestamp;
};

// Irrigation Control Structure
struct IrrigationControl {
  bool zone1Active;
  bool zone2Active;
  bool pumpActive;
  int zone1Duration;  // minutes
  int zone2Duration;  // minutes
  float waterUsed;    // liters
  bool autoMode;
  bool manualOverride;
};

SensorData currentReading;
IrrigationControl irrigationState;

// Thresholds (configurable)
const float MOISTURE_LOW_THRESHOLD = 30.0;    // %
const float MOISTURE_HIGH_THRESHOLD = 70.0;   // %
const float TEMP_HIGH_THRESHOLD = 35.0;       // °C
const int IRRIGATION_MIN_INTERVAL = 30;       // minutes

// Timing Variables
unsigned long lastSensorRead = 0;
unsigned long lastIrrigationCheck = 0;
unsigned long irrigationStartTime = 0;
const unsigned long SENSOR_INTERVAL = 30000;  // 30 seconds
const unsigned long IRRIGATION_CHECK_INTERVAL = 300000; // 5 minutes

void setup() {
  Serial.begin(115200);
  Serial.println("IoT Precision Irrigation System Starting...");
  
  // Initialize Sensors
  dht.begin();
  
  // Initialize Relay Pins
  pinMode(RELAY_1, OUTPUT);
  pinMode(RELAY_2, OUTPUT);
  pinMode(RELAY_3, OUTPUT);
  pinMode(RELAY_4, OUTPUT);
  
  // Initialize all relays OFF
  digitalWrite(RELAY_1, LOW);
  digitalWrite(RELAY_2, LOW);
  digitalWrite(RELAY_3, LOW);
  digitalWrite(RELAY_4, LOW);
  
  // Initialize sensor pins
  pinMode(RAIN_SENSOR, INPUT);
  pinMode(LIGHT_SENSOR, INPUT);
  
  // Initialize WiFi
  connectToWiFi();
  
  // Initialize Web Server Routes
  setupWebServer();
  
  // Initialize irrigation state
  irrigationState.autoMode = true;
  irrigationState.manualOverride = false;
  irrigationState.zone1Active = false;
  irrigationState.zone2Active = false;
  irrigationState.pumpActive = false;
  
  Serial.println("System Initialization Complete");
}

void loop() {
  server.handleClient();
  
  unsigned long currentTime = millis();
  
  // Read sensors at regular intervals
  if (currentTime - lastSensorRead >= SENSOR_INTERVAL) {
    readAllSensors();
    lastSensorRead = currentTime;
    
    // Send data to cloud platform
    sendDataToCloud();
  }
  
  // Check irrigation needs
  if (currentTime - lastIrrigationCheck >= IRRIGATION_CHECK_INTERVAL) {
    if (irrigationState.autoMode && !irrigationState.manualOverride) {
      checkIrrigationNeeds();
    }
    lastIrrigationCheck = currentTime;
  }
  
  // Monitor irrigation duration
  monitorIrrigationDuration();
  
  // Check for emergency conditions
  checkEmergencyConditions();
  
  delay(100);
}

void readAllSensors() {
  // Read soil moisture sensors
  for (int i = 0; i < 5; i++) {
    int sensorPin = SOIL_SENSOR_1 + i;
    if (sensorPin == SOIL_SENSOR_5) sensorPin = SOIL_SENSOR_5; // GPIO36
    
    int rawValue = analogRead(sensorPin);
    // Convert to moisture percentage (calibrated)
    currentReading.soilMoisture[i] = map(rawValue, 0, 4095, 100, 0);
    currentReading.soilMoisture[i] = constrain(currentReading.soilMoisture[i], 0, 100);
  }
  
  // Read DHT22 sensor
  currentReading.temperature = dht.readTemperature();
  currentReading.humidity = dht.readHumidity();
  
  // Read rain sensor
  currentReading.isRaining = !digitalRead(RAIN_SENSOR); // Inverted logic
  
  // Read light sensor
  currentReading.lightIntensity = analogRead(LIGHT_SENSOR);
  
  // Read battery voltage (voltage divider)
  int batteryRaw = analogRead(39); // GPIO39 for battery monitoring
  currentReading.batteryVoltage = (batteryRaw / 4095.0) * 3.3 * 2; // Voltage divider compensation
  
  currentReading.timestamp = millis();
  
  // Print readings to serial monitor
  printSensorReadings();
}

void checkIrrigationNeeds() {
  // Calculate average soil moisture
  float avgMoisture = 0;
  for (int i = 0; i < 5; i++) {
    avgMoisture += currentReading.soilMoisture[i];
  }
  avgMoisture /= 5.0;
  
  Serial.println("Checking irrigation needs...");
  Serial.print("Average soil moisture: ");
  Serial.println(avgMoisture);
  
  // Skip irrigation if raining
  if (currentReading.isRaining) {
    Serial.println("Rain detected - skipping irrigation");
    return;
  }
  
  // Check if irrigation is needed
  if (avgMoisture < MOISTURE_LOW_THRESHOLD) {
    Serial.println("Soil moisture low - starting irrigation");
    startIrrigation();
  } else if (avgMoisture > MOISTURE_HIGH_THRESHOLD) {
    Serial.println("Soil moisture adequate - stopping irrigation");
    stopIrrigation();
  }
}

void startIrrigation() {
  if (!irrigationState.zone1Active) {
    digitalWrite(RELAY_3, HIGH); // Start pump
    digitalWrite(RELAY_1, HIGH); // Open zone 1 valve
    
    irrigationState.pumpActive = true;
    irrigationState.zone1Active = true;
    irrigationStartTime = millis();
    irrigationState.zone1Duration = 15; // 15 minutes default
    
    Serial.println("Irrigation started - Zone 1");
  }
}

void stopIrrigation() {
  digitalWrite(RELAY_1, LOW);
  digitalWrite(RELAY_2, LOW);
  digitalWrite(RELAY_3, LOW);
  
  irrigationState.zone1Active = false;
  irrigationState.zone2Active = false;
  irrigationState.pumpActive = false;
  
  Serial.println("Irrigation stopped");
}

void monitorIrrigationDuration() {
  if (irrigationState.pumpActive) {
    unsigned long elapsed = (millis() - irrigationStartTime) / 60000; // Convert to minutes
    
    // Stop irrigation after set duration
    if (elapsed >= irrigationState.zone1Duration) {
      stopIrrigation();
      Serial.println("Irrigation completed - duration limit reached");
    }
    
    // Safety timeout (30 minutes max)
    if (elapsed >= 30) {
      stopIrrigation();
      Serial.println("Emergency stop - maximum duration exceeded");
    }
  }
}

void checkEmergencyConditions() {
  // High temperature protection
  if (currentReading.temperature > TEMP_HIGH_THRESHOLD) {
    if (!irrigationState.pumpActive && !currentReading.isRaining) {
      Serial.println("High temperature detected - emergency irrigation");
      startIrrigation();
    }
  }
  
  // Low battery protection
  if (currentReading.batteryVoltage < 11.0) {
    Serial.println("Low battery - entering power save mode");
    // Implement power saving measures
  }
}

void connectToWiFi() {
  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println();
  Serial.println("WiFi connected!");
  Serial.print("IP address: ");
  Serial.println(WiFi.localIP());
}

void setupWebServer() {
  // Main dashboard
  server.on("/", handleRoot);
  
  // API endpoints
  server.on("/api/sensors", handleSensorData);
  server.on("/api/irrigation/start", handleStartIrrigation);
  server.on("/api/irrigation/stop", handleStopIrrigation);
  server.on("/api/config", handleConfig);
  
  server.begin();
  Serial.println("Web server started");
}

void handleRoot() {
  String html = generateDashboardHTML();
  server.send(200, "text/html", html);
}

void handleSensorData() {
  DynamicJsonDocument doc(1024);
  
  JsonArray soilArray = doc.createNestedArray("soilMoisture");
  for (int i = 0; i < 5; i++) {
    soilArray.add(currentReading.soilMoisture[i]);
  }
  
  doc["temperature"] = currentReading.temperature;
  doc["humidity"] = currentReading.humidity;
  doc["lightIntensity"] = currentReading.lightIntensity;
  doc["isRaining"] = currentReading.isRaining;
  doc["batteryVoltage"] = currentReading.batteryVoltage;
  doc["timestamp"] = currentReading.timestamp;
  
  // Irrigation status
  doc["irrigationActive"] = irrigationState.pumpActive;
  doc["autoMode"] = irrigationState.autoMode;
  
  String response;
  serializeJson(doc, response);
  server.send(200, "application/json", response);
}

void handleStartIrrigation() {
  if (server.hasArg("zone")) {
    int zone = server.arg("zone").toInt();
    int duration = server.hasArg("duration") ? server.arg("duration").toInt() : 15;
    
    irrigationState.manualOverride = true;
    
    if (zone == 1) {
      digitalWrite(RELAY_3, HIGH);
      digitalWrite(RELAY_1, HIGH);
      irrigationState.zone1Active = true;
      irrigationState.zone1Duration = duration;
    } else if (zone == 2) {
      digitalWrite(RELAY_3, HIGH);
      digitalWrite(RELAY_2, HIGH);
      irrigationState.zone2Active = true;
      irrigationState.zone2Duration = duration;
    }
    
    irrigationState.pumpActive = true;
    irrigationStartTime = millis();
    
    server.send(200, "text/plain", "Irrigation started");
    Serial.println("Manual irrigation started - Zone " + String(zone));
  } else {
    server.send(400, "text/plain", "Zone parameter required");
  }
}

void handleStopIrrigation() {
  stopIrrigation();
  irrigationState.manualOverride = false;
  server.send(200, "text/plain", "Irrigation stopped");
  Serial.println("Manual irrigation stopped");
}

void handleConfig() {
  if (server.method() == HTTP_POST) {
    // Handle configuration updates
    if (server.hasArg("autoMode")) {
      irrigationState.autoMode = server.arg("autoMode") == "true";
    }
    server.send(200, "text/plain", "Configuration updated");
  } else {
    // Return current configuration
    DynamicJsonDocument doc(512);
    doc["autoMode"] = irrigationState.autoMode;
    doc["moistureLowThreshold"] = MOISTURE_LOW_THRESHOLD;
    doc["moistureHighThreshold"] = MOISTURE_HIGH_THRESHOLD;
    
    String response;
    serializeJson(doc, response);
    server.send(200, "application/json", response);
  }
}

String generateDashboardHTML() {
  String html = R"(
<!DOCTYPE html>
<html>
<head>
    <title>IoT Precision Irrigation Dashboard</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial; margin: 20px; background-color: #f0f8ff; }
        .container { max-width: 1200px; margin: auto; }
        .card { background: white; padding: 20px; margin: 10px; border-radius: 10px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .sensor-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 15px; }
        .sensor-value { font-size: 2em; font-weight: bold; color: #2c3e50; }
        .status-active { color: #27ae60; }
        .status-inactive { color: #e74c3c; }
        button { padding: 10px 20px; margin: 5px; border: none; border-radius: 5px; cursor: pointer; }
        .btn-start { background: #27ae60; color: white; }
        .btn-stop { background: #e74c3c; color: white; }
        .btn-auto { background: #3498db; color: white; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🌱 IoT Precision Irrigation System</h1>
        
        <div class="card">
            <h2>System Status</h2>
            <div id="systemStatus">Loading...</div>
        </div>
        
        <div class="sensor-grid">
            <div class="card">
                <h3>Soil Moisture</h3>
                <div id="soilMoisture" class="sensor-value">---%</div>
            </div>
            <div class="card">
                <h3>Temperature</h3>
                <div id="temperature" class="sensor-value">---°C</div>
            </div>
            <div class="card">
                <h3>Humidity</h3>
                <div id="humidity" class="sensor-value">---%</div>
            </div>
            <div class="card">
                <h3>Light Intensity</h3>
                <div id="lightIntensity" class="sensor-value">---</div>
            </div>
        </div>
        
        <div class="card">
            <h2>Irrigation Control</h2>
            <button onclick="startIrrigation(1)" class="btn-start">Start Zone 1</button>
            <button onclick="startIrrigation(2)" class="btn-start">Start Zone 2</button>
            <button onclick="stopIrrigation()" class="btn-stop">Stop All</button>
            <button onclick="toggleAutoMode()" id="autoBtn" class="btn-auto">Auto Mode</button>
        </div>
    </div>
    
    <script>
        function updateSensorData() {
            fetch('/api/sensors')
                .then(response => response.json())
                .then(data => {
                    // Calculate average soil moisture
                    let avgMoisture = data.soilMoisture.reduce((a, b) => a + b, 0) / data.soilMoisture.length;
                    document.getElementById('soilMoisture').textContent = avgMoisture.toFixed(1) + '%';
                    
                    document.getElementById('temperature').textContent = data.temperature.toFixed(1) + '°C';
                    document.getElementById('humidity').textContent = data.humidity.toFixed(1) + '%';
                    document.getElementById('lightIntensity').textContent = data.lightIntensity;
                    
                    // Update system status
                    let status = data.irrigationActive ? 
                        '<span class="status-active">🟢 Irrigation Active</span>' : 
                        '<span class="status-inactive">🔴 Irrigation Inactive</span>';
                    
                    if (data.isRaining) status += ' | 🌧️ Rain Detected';
                    if (data.autoMode) status += ' | 🤖 Auto Mode';
                    
                    document.getElementById('systemStatus').innerHTML = status;
                });
        }
        
        function startIrrigation(zone) {
            fetch(`/api/irrigation/start?zone=${zone}&duration=15`)
                .then(response => response.text())
                .then(data => alert(data));
        }
        
        function stopIrrigation() {
            fetch('/api/irrigation/stop')
                .then(response => response.text())
                .then(data => alert(data));
        }
        
        function toggleAutoMode() {
            // Implementation for auto mode toggle
            fetch('/api/config', {method: 'POST', body: 'autoMode=true'})
                .then(response => response.text())
                .then(data => alert(data));
        }
        
        // Update data every 30 seconds
        setInterval(updateSensorData, 30000);
        updateSensorData(); // Initial load
    </script>
</body>
</html>
)";
  return html;
}

void sendDataToCloud() {
  // Implementation for sending data to cloud platform (AWS IoT, Firebase, etc.)
  // This would include authentication and data formatting
  Serial.println("Sending data to cloud...");
}

void printSensorReadings() {
  Serial.println("=== Sensor Readings ===");
  Serial.print("Soil Moisture Sensors: ");
  for (int i = 0; i < 5; i++) {
    Serial.print(currentReading.soilMoisture[i]);
    Serial.print("% ");
  }
  Serial.println();
  Serial.printf("Temperature: %.1f°C\n", currentReading.temperature);
  Serial.printf("Humidity: %.1f%%\n", currentReading.humidity);
  Serial.printf("Light: %d\n", currentReading.lightIntensity);
  Serial.printf("Rain: %s\n", currentReading.isRaining ? "Yes" : "No");
  Serial.printf("Battery: %.1fV\n", currentReading.batteryVoltage);
  Serial.println("========================");
}
