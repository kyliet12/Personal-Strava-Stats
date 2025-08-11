"use client";

import { useEffect, useState } from "react";
import { Bar } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

type Activity = {
  id: number;
  name: string;
  type: string;
  distance: number;
  start_date_local: string;
};

export default function Dashboard() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/strava")
      .then((res) => res.json())
      .then((data) => {
        setActivities(data.activities || []);
        setLoading(false);
      })
      .catch((err) => {
        setError("Failed to load activities");
        setLoading(false);
      });
  }, []);

  if (loading) return <div>Loading...</div>;
  if (error) return <div>{error}</div>;

  // Example: total distance and a simple bar chart (placeholder)
  const totalDistance = activities.reduce((sum, a) => sum + (a.distance || 0), 0) / 1609;
  const runActivities = activities.filter((a) => a.type === "Run");
  const rideActivities = activities.filter((a) => a.type === "Ride");
  const swimActivities = activities.filter((a) => a.type === "Swim");

  // --- Weekly mileage chart data ---
  // Group runActivities by week (ISO week)
  const weekMap: { [week: string]: number } = {};
  runActivities.forEach((a) => {
    const date = new Date(a.start_date_local);
    // Get ISO week string: YYYY-Www
    const year = date.getFullYear();
    const week = getISOWeek(date);
    const key = `${year}-W${week.toString().padStart(2, "0")}`;
    weekMap[key] = (weekMap[key] || 0) + a.distance / 1609;
  });
  const weekLabels = Object.keys(weekMap).sort();
  const weekData = weekLabels.map((w) => weekMap[w]);

  function getISOWeek(date: Date) {
    const tmp = new Date(date.getTime());
    tmp.setHours(0, 0, 0, 0);
    tmp.setDate(tmp.getDate() + 4 - (tmp.getDay() || 7));
    const yearStart = new Date(tmp.getFullYear(), 0, 1);
    const weekNo = Math.ceil(((tmp.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
    return weekNo;
  }

  return (
    <main style={{ padding: 24 }}>
      <h1>Strava Dashboard</h1>
      <div style={{ marginBottom: 24 }}>
        <strong>Total Distance:</strong> {totalDistance.toFixed(2)} miles
      </div>
      <div style={{ display: "flex", gap: 32 }}>
        <div>
          <h2>Runs</h2>
          <p>Count: {runActivities.length}</p>
        </div>
        <div>
          <h2>Rides</h2>
          <p>Count: {rideActivities.length}</p>
        </div>
        <div>
          <h2>Swims</h2>
          <p>Count: {swimActivities.length}</p>
        </div>
      </div>
      <div style={{ marginTop: 40 }}>
        <h2>Weekly Running Mileage</h2>
        <Bar
          data={{
            labels: weekLabels,
            datasets: [
              {
                label: "Miles per Week",
                data: weekData,
                backgroundColor: "#36a2eb",
              },
            ],
          }}
          options={{
            responsive: true,
            plugins: {
              legend: { display: false },
              title: { display: true, text: "Weekly Running Mileage" },
            },
            scales: {
              x: { title: { display: true, text: "Week" } },
              y: { title: { display: true, text: "Miles" } },
            },
          }}
        />
      </div>
      <div style={{ marginTop: 40 }}>
        <h2>Recent Activities</h2>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr>
              <th style={{ borderBottom: "1px solid #ccc" }}>Name</th>
              <th style={{ borderBottom: "1px solid #ccc" }}>Type</th>
              <th style={{ borderBottom: "1px solid #ccc" }}>Distance (mi)</th>
              <th style={{ borderBottom: "1px solid #ccc" }}>Date</th>
            </tr>
          </thead>
          <tbody>
            {activities.slice(0, 20).map((a) => (
              <tr key={a.id}>
                <td>{a.name}</td>
                <td>{a.type}</td>
                <td>{(a.distance / 1609).toFixed(2)}</td>
                <td>{a.start_date_local?.slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </main>
  );
}
