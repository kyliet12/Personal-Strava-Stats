
"use client";
import { MapContainer, TileLayer, Polyline } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useState } from "react";
import polyline from "polyline";

type Activity = {
    id: number;
    name: string;
    type: string;
    map?: { summary_polyline?: string };
};

const colorMap: Record<string, string> = {
    Ride: "red",
    Run: "blue",
    Walk: "purple",
};

export default function ActivityMap() {
    const [activities, setActivities] = useState<Activity[]>([]);

    useEffect(() => {
        fetch("/api/strava")
            .then((res) => res.json())
            .then((data) => {
                setActivities((data.activities || []).filter((a: any) => a.map && a.map.summary_polyline));
            });
    }, []);

    // Gather all coordinates for centering
    const allCoords = activities
        .map((a) => (a.map?.summary_polyline ? polyline.decode(a.map.summary_polyline) : []))
        .flat();
    const center =
        allCoords.length > 0
            ? [
                    allCoords.reduce((sum, c) => sum + c[0], 0) / allCoords.length,
                    allCoords.reduce((sum, c) => sum + c[1], 0) / allCoords.length,
                ]
            : [39, -98]; // fallback: center of US

    return (
        <main className="p-8">
            <h1 className="text-2xl font-bold mb-4">Activity Map</h1>
            <div style={{ height: 600, width: "100%" }}>
                <MapContainer center={center as [number, number]} zoom={5} style={{ height: "100%", width: "100%" }}>
                    <TileLayer
                        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                        attribution="&copy; OpenStreetMap contributors"
                    />
                    {activities.map((a) => {
                        if (!a.map?.summary_polyline) return null;
                        const coords = polyline.decode(a.map.summary_polyline);
                        const color = colorMap[a.type] || "gray";
                        return <Polyline key={a.id} positions={coords} pathOptions={{ color, weight: 4, opacity: 0.5 }} />;
                    })}
                </MapContainer>
            </div>
        </main>
    );
}