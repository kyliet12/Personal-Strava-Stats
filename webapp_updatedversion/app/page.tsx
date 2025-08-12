"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

type Activity = {
  id: number;
  name: string;
  type: string;
  distance: number;
  start_date_local: string;
  moving_time: number;
};

export default function Home() {
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

  // Build last 4 weeks calendar grid
  const today = new Date();
  const start = new Date(today);
  start.setHours(0, 0, 0, 0);
  // Find the most recent Monday
  const dayOfWeek = start.getDay(); // 0 (Sun) - 6 (Sat)
  const daysSinceMonday = (dayOfWeek + 6) % 7;
  start.setDate(today.getDate() - daysSinceMonday - 28); // 4 weeks ago, start on Monday
  const daysLeftInWeek = 6 - daysSinceMonday;
  const days: string[] = [];
  for (let i = 0; i < (29+daysLeftInWeek); i++) {
    const d = new Date(start);
    d.setDate(start.getDate() + i);
    const dateStr = d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
    days.push(dateStr);
  }

  // Group activities by date string (YYYY-MM-DD)
  const activityMap: { [date: string]: Activity[] } = {};
  activities.forEach((a) => {
    const dateStr = a.start_date_local.slice(0, 10);
    if (!activityMap[dateStr]) activityMap[dateStr] = [];
    activityMap[dateStr].push(a);
  });

  return (
    <div className="min-h-screen flex flex-col">
      <main className="flex-1 flex flex-col items-center justify-center text-center p-8">
        <h1 className="text-4xl font-bold mb-4">Welcome to Your Strava Stats!</h1>
        <p className="text-lg mb-8 max-w-xl">
          This site lets you view your latest Strava activity stats, charts, and more. Use the navigation bar above to access your dashboard and explore your data.
        </p>
        <Link href="/dashboard" className="bg-orange-600 text-white px-6 py-3 rounded shadow hover:bg-orange-700 transition">
          Go to Dashboard
        </Link>
      </main>
      <div className="calendar p-8">
        {/* <h1 className="text-2xl font-bold mb-4">Last 4 Weeks of Activity</h1> */}
        {loading ? (
          <div>Loading calendar...</div>
        ) : error ? (
          <div className="text-red-500">{error}</div>
        ) : (
          <div className="grid grid-cols-7 gap-2">
            {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => (
              <div key={d} className="font-bold text-center">{d}</div>
            ))}
            {days.map((dateStr) => {
              const dayNum = Number(dateStr.slice(-2))
              const acts = activityMap[dateStr] || [];
              return (
                <div key={dateStr} className="border rounded min-h-[80px] p-1 flex flex-col items-center bg-white">
                  <div className="text-xs text-gray-500 mb-1">{dayNum}</div>
                  {acts.map((a) => {
                    let bg = "bg-gray-200 text-gray-700";
                    if (a.type === "Run") bg = "bg-blue-100 text-blue-800";
                    if (a.type === "Ride") bg = "bg-red-100 text-red-800";
                    if (a.type === "Swim") bg = "bg-green-100 text-green-800";
                    return (
                      <div
                        key={a.id}
                        className={`w-full mb-1 px-1 py-0.5 rounded text-xs truncate ${bg}`}
                        title={a.name}
                      >
                        {a.type}: {(a.distance/1609).toFixed(1)} mi ({(a.moving_time/60).toFixed(1)} min)
                      </div>
                    );
                  })}
                </div>
              );
            })}
          </div>
        )}
      </div>
      <footer className="bg-gray-100 text-gray-500 text-center py-4">
        &copy; {new Date().getFullYear()} Personal Strava Stats
      </footer>
    </div>
  );
}
