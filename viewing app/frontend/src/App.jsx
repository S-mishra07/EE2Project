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
    <div className="min-h-screen bg-gray-100 p-6">
      <h1 className="text-2xl font-bold mb-4 text-center">secret power energy tracker</h1>
      <div className="space-y-4 max-w-xl mx-auto">
        {jobs.map((job) => (
          <div
            key={job._id}
            className="bg-white p-4 rounded shadow flex justify-between items-center"
          >
            <div>
              <h2 className="text-lg font-semibold">{"the energy input is : " + job.Energy_in || "Untitled Job"}</h2>
              <h2 className="text-sm text-gray-500">{"the energy output is : " + job.Energy_out || "Unknown Company"}</h2>
              <h2 className="text-sm text-gray-500">{"the economics are : " + job.Economics || "Unknown Company"}</h2>
              <h2 className="text-sm text-gray-500">{"the internal variables are : " + job.Internal_variables || "Unknown Company"}</h2>
            </div>
            <button
              onClick={() => deleteJob(job._id)}
              className="bg-red-500 hover:bg-red-600 text-white px-3 py-1 rounded"
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export default App;
