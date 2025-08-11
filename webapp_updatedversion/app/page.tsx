
import Link from "next/link";

export default function Home() {
  return (
    <div className="min-h-screen flex flex-col">
      
      <main className="flex-1 flex flex-col items-center justify-center text-center p-8">
        <h1 className="text-4xl font-bold mb-4">Welcome to Your Strava Stats!</h1>
        <p className="text-lg mb-8 max-w-xl">
          This site lets you view your latest Strava activity stats, charts, and more. Use the navigation bar above to access your dashboard and explore your data.
        </p>
        <Link href="/dashboard" className="bg-blue-600 text-white px-6 py-3 rounded shadow hover:bg-blue-700 transition">
          Go to Dashboard
        </Link>
      </main>
      <footer className="bg-gray-100 text-gray-500 text-center py-4">
        &copy; {new Date().getFullYear()} Personal Strava Stats
      </footer>
    </div>
  );
}
