import { useEffect, useState } from "react";
import axios from "axios";

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
    <div className="min-h-screen bg-gray-100 p-8">
      <h1 className="text-4xl font-bold mb-8 text-center">Secret Power Energy Tracker</h1>
      <div className="space-y-6 max-w-4xl mx-auto">
        {jobs.map((job) => (
          <div
            key={job._id}
            className="bg-white p-6 rounded-lg shadow-lg"
          >
            <div className="grid grid-cols-1 gap-4 mb-6">
              <div className="border-2 border-gray-300 p-4 rounded-lg">
                <h2 className="text-2xl font-bold mb-2">Energy Input</h2>
                <p className="text-xl text-gray-800">{job.Energy_in || "Not specified"}</p>
              </div>
              
              <div className="border-2 border-gray-300 p-4 rounded-lg">
                <h2 className="text-2xl font-bold mb-2">Energy Output</h2>
                <p className="text-xl text-gray-800">{job.Energy_out || "Not specified"}</p>
              </div>
              
              <div className="border-2 border-gray-300 p-4 rounded-lg">
                <h2 className="text-2xl font-bold mb-2">Economics</h2>
                <p className="text-xl text-gray-800">{job.Economics || "Not specified"}</p>
              </div>
              
              <div className="border-2 border-gray-300 p-4 rounded-lg">
                <h2 className="text-2xl font-bold mb-2">Internal Variables</h2>
                <p className="text-xl text-gray-800">{job.Internal_variables || "Not specified"}</p>
              </div>
            </div>
            
            <div className="flex justify-end">
              <button
                onClick={() => fetchJobs()}
                className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg text-lg font-semibold"
              >
                Refresh
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;