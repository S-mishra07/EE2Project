import { useEffect, useState } from "react";
import axios from "axios";
import { RefreshCw, Zap, TrendingUp, DollarSign, Settings } from "lucide-react";

function App() {
  const [jobs, setJobs] = useState([]);

  const fetchJobs = async () => {
    try {
      const res = await axios.get("http://localhost:3000/find");
      setJobs(res.data.data);
    } catch (err) {
      console.error("Failed to fetch jobs:", err);
    }
  };

  const deleteJob = async (id) => {
    try {
      await axios.delete(`http://localhost:3000/find/${id}`);
      setJobs((prev) => prev.filter((job) => job._id !== id));
    } catch (err) {
      console.error("Failed to delete job:", err);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  return (
    <div className="min-h-screen bg-gray-50 py-10 px-4 sm:px-8">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-4xl font-extrabold text-center text-gray-800 mb-6">
          ⚡ Secret Power Energy Tracker
        </h1>

        <div className="flex justify-center mb-8">
          <button
            onClick={fetchJobs}
            className="flex items-center gap-2 bg-blue-600 hover:bg-blue-700 text-white px-5 py-2 rounded-lg shadow transition duration-200"
          >
            <RefreshCw className="w-5 h-5" />
            Refresh Data
          </button>
        </div>

        {jobs.length === 0 ? (
          <p className="text-center text-gray-500 text-lg">No jobs found. Try refreshing.</p>
        ) : (
          <div className="space-y-8">
            {jobs.map((job) => (
              <div
                key={job._id}
                className="bg-white p-6 rounded-2xl shadow-xl border border-gray-200 transition hover:shadow-2xl"
              >
                <div className="grid sm:grid-cols-2 gap-6 mb-6">
                  <InfoCard icon={<Zap className="text-yellow-500" />} title="Energy Input" value={job.Energy_in} />
                  <InfoCard icon={<TrendingUp className="text-green-500" />} title="Energy Output" value={job.Energy_out} />
                  <InfoCard icon={<DollarSign className="text-blue-500" />} title="Economics" value={job.Economics} />
                  <InfoCard icon={<Settings className="text-purple-500" />} title="Internal Variables" value={job.Internal_variables} />
                </div>

                <div className="flex justify-end">
                  <button
                    onClick={() => deleteJob(job._id)}
                    className="text-red-600 hover:text-red-800 font-semibold transition"
                  >
                    Delete Entry
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function InfoCard({ icon, title, value }) {
  return (
    <div className="p-4 bg-gray-100 rounded-xl border border-gray-300">
      <div className="flex items-center gap-3 mb-2">
        {icon}
        <h2 className="text-lg font-bold text-gray-700">{title}</h2>
      </div>
      <p className="text-gray-800 text-md">{value || "Not specified"}</p>
    </div>
  );
}

export default App;
