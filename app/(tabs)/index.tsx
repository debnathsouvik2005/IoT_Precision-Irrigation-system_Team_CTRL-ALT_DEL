import { initializeApp } from "firebase/app";
import { getDatabase, onChildAdded, ref } from "firebase/database";
import React, { useEffect, useState } from "react";
import { Button, Dimensions, ScrollView, StyleSheet, Text, View } from "react-native";
import { LineChart } from "react-native-chart-kit";
import { MaterialIcons } from '@expo/vector-icons';


// Firebase config
const firebaseConfig = {
  apiKey: "AIzaSyB9CjbnA8IbaGDtFzMhTqjJudWHzymv37o",
  authDomain: "precision-irrigation-dec40.firebaseapp.com",
  databaseURL: "https://precision-irrigation-dec40-default-rtdb.asia-southeast1.firebasedatabase.app",
  projectId: "precision-irrigation-dec40",
  storageBucket: "precision-irrigation-dec40.firebasestorage.app",
  messagingSenderId: "766426949461",
  appId: "1:766426949461:web:62490bc75f190be6b4f1dc",
  measurementId: "G-WZMPCT8FQ5",
};


const app = initializeApp(firebaseConfig);
const database = getDatabase(app);


// Helper to ensure valid numbers for charts
const safeNumber = (value: any): number => {
  const parsed = parseFloat(value);
  return !isNaN(parsed) && isFinite(parsed) ? parsed : 0;
};


export default function App() {
  const [sensorData, setSensorData] = useState<{
    soil_moisture: number | string;
    temperature: number | string;
    humidity: number | string;
    lightIntensity: number | string;
    isRaining: boolean;
  }>({
    soil_moisture: 0,
    temperature: 0,
    humidity: 0,
    lightIntensity: 0,
    isRaining: false,
  });


  const [labels, setLabels] = useState<string[]>(["Start"]);
  const [moistureData, setMoistureData] = useState<number[]>([0]);
  const [tempData, setTempData] = useState<number[]>([0]);
  const [humidityData, setHumidityData] = useState<number[]>([0]);


  // ML Prediction States
  const [irrigationNeeded, setIrrigationNeeded] = useState<string>("Analyzing...");
  const [recommendedDuration, setRecommendedDuration] = useState<string>("-- min");
  const [confidence, setConfidence] = useState<string>("-- %");
  const [recommendations, setRecommendations] = useState<string[]>(["Waiting for data..."]);


  // Simulated ML model call (replace with your real API call)
  async function fetchIrrigationPrediction(sensor: typeof sensorData) {
    const needed = sensor.soil_moisture !== "--" && Number(sensor.soil_moisture) < 40;
    const duration = needed
      ? Math.max(5, Math.round((40 - Number(sensor.soil_moisture)) * 0.5 + Math.random() * 5))
      : 0;
    const conf = Math.round(70 + Math.random() * 25);


    const recs = [];
    if (Number(sensor.soil_moisture) < 20) recs.push("Critical: Soil moisture very low - irrigate immediately");
    else if (Number(sensor.soil_moisture) < 40) recs.push("Soil moisture low - irrigate soon");
    else recs.push("Soil moisture adequate - no irrigation needed now");
    if (Number(sensor.temperature) > 32) recs.push("High temperature - consider extra watering");
    if (sensor.isRaining) recs.push("Rain detected - consider reducing irrigation duration");


    return {
      irrigation_needed: needed,
      duration_minutes: duration,
      confidence: conf,
      recommendations: recs,
    };
  }


  // Update ML predictions state variables
  function updateMLPredictions(data: typeof sensorData) {
    fetchIrrigationPrediction(data).then((prediction) => {
      setIrrigationNeeded(prediction.irrigation_needed ? "Yes" : "No");
      setRecommendedDuration(prediction.duration_minutes + " min");
      setConfidence(prediction.confidence + " %");
      setRecommendations(prediction.recommendations);
    });
  }


  useEffect(() => {
    const sensorRef = ref(database, "sensorData");
    onChildAdded(sensorRef, (snapshot) => {
      const data = snapshot.val();
      if (data) {
        const time = new Date().toLocaleTimeString();


        const soil = safeNumber(data.soil_moisture);
        const temp = safeNumber(data.temperature);
        const hum = safeNumber(data.humidity);
        const light = safeNumber(data.lightIntensity);


        const sensorUpdate = {
          soil_moisture: soil > 0 ? soil : "--",
          temperature: temp > 0 ? temp : "--",
          humidity: hum > 0 ? hum : "--",
          lightIntensity: light > 0 ? light : "--",
          isRaining: data.isRaining === true,
        };


        setSensorData(sensorUpdate);


        updateMLPredictions(sensorUpdate);


        setLabels((prev) => [...prev.slice(-9), time]);
        setMoistureData((prev) => [...prev.slice(-9), soil]);
        setTempData((prev) => [...prev.slice(-9), temp]);
        setHumidityData((prev) => [...prev.slice(-9), hum]);
      }
    });
  }, []);


  // Show only alternate X-axis labels
  const getAlternateLabels = (allLabels: string[]) =>
    allLabels.map((lbl, idx) => (idx % 2 === 0 ? lbl : ""));


  return (
    <ScrollView contentContainerStyle={styles.container}>
      <Text style={styles.title}>🌱 Krishi: Smart Farming</Text>
      <Text style={styles.subtitle}>Precision Agriculture Dashboard</Text>


      {/* Sensor Cards */}
      <View style={styles.cardsRow}>
        <View style={styles.card}>
          <Text style={styles.label}>Soil Moisture</Text>
          <Text style={styles.value}>
            {typeof sensorData.soil_moisture === "number"
              ? sensorData.soil_moisture + "%"
              : "--%"}
          </Text>
        </View>
        <View style={styles.card}>
          <Text style={styles.label}>Temperature</Text>
          <Text style={styles.value}>
            {typeof sensorData.temperature === "number"
              ? sensorData.temperature + "°C"
              : "--°C"}
          </Text>
        </View>
      </View>
      <View style={styles.cardsRow}>
        <View style={styles.card}>
          <Text style={styles.label}>Humidity</Text>
          <Text style={styles.value}>
            {typeof sensorData.humidity === "number"
              ? sensorData.humidity + "%"
              : "--%"}
          </Text>
        </View>
        <View style={styles.card}>
          <Text style={styles.label}>Light</Text>
          <Text style={styles.value}>
            {typeof sensorData.lightIntensity === "number"
              ? sensorData.lightIntensity
              : "--"}
          </Text>
        </View>
      </View>
      <View style={styles.cardsRow}>
        <View style={styles.card}>
          <Text style={styles.label}>Rain Status</Text>
          <Text style={styles.value}>
            {sensorData.isRaining ? "🌧️ Yes" : "☀️ No"}
          </Text>
        </View>
      </View>


      {/* ML Prediction Cards */}
      <View style={styles.cardsRow}>
        <View style={[styles.card, styles.predictionCard]}>
          <Text style={styles.label}>Irrigation Needed</Text>
          <Text style={styles.value}>{irrigationNeeded}</Text>
        </View>
        <View style={[styles.card, styles.predictionCard]}>
          <Text style={styles.label}>Recommended Duration</Text>
          <Text style={styles.value}>{recommendedDuration}</Text>
        </View>
        <View style={[styles.card, styles.predictionCard]}>
          <Text style={styles.label}>Confidence</Text>
          <Text style={styles.value}>{confidence}</Text>
        </View>
      </View>


      <View style={styles.mlRecommendationBox}>
        <View style={styles.mlHeader}>
          <Text style={styles.mlIcon}>🤖</Text>
          <Text style={styles.mlHeaderText}>AI Irrigation Recommendations</Text>
        </View>
        <View style={styles.recommendationsList}>
          {recommendations.map((rec, idx) => (
            <View key={idx} style={styles.recRow}>
              <MaterialIcons
                name="lightbulb-outline"
                size={18}
                color="#2ecc71"
                style={styles.recIcon}
              />
              <Text style={styles.recText}>{rec}</Text>
            </View>
          ))}
        </View>
      </View>


      {/* Charts */}
      {labels.length > 0 && moistureData.length > 0 && (
        <>
          <Text style={styles.chartTitle}>📊 Trends</Text>


          <LineChart
            data={{
              labels: getAlternateLabels(labels),
              datasets: [{ data: moistureData }],
            }}
            width={Dimensions.get("window").width - 30}
            height={220}
            yAxisSuffix="%"
            chartConfig={chartConfig}
            style={styles.chart}
            bezier
          />


          <LineChart
            data={{
              labels: getAlternateLabels(labels),
              datasets: [{ data: tempData }],
            }}
            width={Dimensions.get("window").width - 30}
            height={220}
            yAxisSuffix="°C"
            chartConfig={chartConfig}
            style={styles.chart}
            bezier
          />


          <LineChart
            data={{
              labels: getAlternateLabels(labels),
              datasets: [{ data: humidityData }],
            }}
            width={Dimensions.get("window").width - 30}
            height={220}
            yAxisSuffix="%"
            chartConfig={chartConfig}
            style={styles.chart}
            bezier
          />
        </>
      )}


      <View style={styles.buttonBox}>
        <Button title="🔄 Refresh" onPress={() => {}} />
        <Button title="💧 Irrigate" onPress={() => {}} />
        <Button title="📜 History" onPress={() => {}} />
      </View>
    </ScrollView>
  );
}


const chartConfig = {
  backgroundColor: "#ffffff",
  backgroundGradientFrom: "#f4f9f4",
  backgroundGradientTo: "#e6f7e6",
  decimalPlaces: 1,
  color: (opacity = 1) => `rgba(45, 106, 79, ${opacity})`,
  labelColor: (opacity = 1) => `rgba(0,0,0,${opacity})`,
  style: { borderRadius: 16 },
  propsForDots: { r: "5", strokeWidth: "2", stroke: "#2d6a4f" },
};


const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    padding: 20,
    backgroundColor: "#f4f9f4",
  },
  title: {
    fontSize: 28,
    fontWeight: "bold",
    textAlign: "center",
    color: "#2d6a4f",
  },
  subtitle: {
    fontSize: 16,
    textAlign: "center",
    marginBottom: 20,
    color: "#40916c",
  },
  cardsRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: 15,
  },
  card: {
    flex: 1,
    backgroundColor: "white",
    marginHorizontal: 5,
    padding: 20,
    borderRadius: 12,
    shadowColor: "#000",
    shadowOpacity: 0.1,
    shadowOffset: { width: 0, height: 2 },
    shadowRadius: 4,
    elevation: 3,
  },
  label: {
    fontSize: 14,
    color: "#1b4332",
    marginBottom: 5,
    fontWeight: "600",
  },
  value: {
    fontSize: 20,
    fontWeight: "bold",
    color: "#007acc",
  },
  predictionCard: {
    flex: 1,
    backgroundColor: "#d0f0fd",
    borderRadius: 12,
    marginHorizontal: 5,
    padding: 20,
    justifyContent: "center",
    alignItems: "center",
  },
  mlRecommendationBox: {
    backgroundColor: "#eaf6fb",
    borderRadius: 16,
    padding: 20,
    marginTop: 24,
    shadowColor: "#007acc",
    shadowOpacity: 0.15,
    shadowOffset: { width: 0, height: 2 },
    shadowRadius: 8,
    elevation: 3,
  },
  mlHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 16,
  },
  mlIcon: {
    fontSize: 26,
    marginRight: 10,
  },
  mlHeaderText: {
    fontSize: 20,
    fontWeight: "600",
    color: "#007acc",
  },
  recommendationsList: {
    marginTop: 6,
  },
  recRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: 12,
  },
  recIcon: {
    marginRight: 8,
  },
  recText: {
    fontSize: 16,
    color: "#244a5e",
    flex: 1,
    fontWeight: "500",
    lineHeight: 23,
  },
  chartTitle: {
    fontSize: 20,
    marginVertical: 15,
    fontWeight: "600",
    textAlign: "center",
    color: "#2c3e50",
  },
  chart: {
    borderRadius: 12,
    marginVertical: 10,
  },
  buttonBox: {
    marginVertical: 20,
    flexDirection: "row",
    justifyContent: "space-around",
  },
});
