import { useEffect, useState } from 'react';
import { Sun, DollarSign, Activity } from 'lucide-react';

export default function App() {
  const [currentData, setCurrentData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    
    const fetchLatest = async () => {
      try {
        const res = await fetch('http://localhost:3000/latest');
        const data = await res.json();
        setCurrentData(data);
        setLoading(false);
      } catch (error) {
        console.error('Initial fetch error:', error);
      }
    };
    fetchLatest();

    
    const ws = new WebSocket('ws://localhost:3000');
    
    ws.onmessage = (event) => {
      const newData = JSON.parse(event.data);
      setCurrentData(newData);
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };

    return () => ws.close();
  }, []);

  if (loading) return <div className="p-8">Loading initial data...</div>;
  if (!currentData) return <div className="p-8">No data available</div>;

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-3xl font-bold mb-8">Smart Grid Dashboard</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <DataCard
          icon={<Sun className="text-yellow-500" />}
          title="Solar Energy"
          value={currentData.sun}
          unit="kW"
        />
        <DataCard
          icon={<DollarSign className="text-green-500" />}
          title="Buy Price"
          value={currentData.price.buy}
          unit="$"
        />
        <DataCard
          icon={<DollarSign className="text-blue-500" />}
          title="Sell Price"
          value={currentData.price.sell}
          unit="$"
        />
        <DataCard
          icon={<Activity className="text-purple-500" />}
          title="Demand"
          value={currentData.demand.toFixed(2)}
          unit="kW"
        />
        <div className="bg-white p-6 rounded-xl shadow-md">
          <h3 className="text-lg font-semibold mb-2">Current Tick</h3>
          <p className="text-2xl font-bold">{currentData.tick}</p>
          <p className="text-sm text-gray-500 mt-2">
            Updated: {new Date(currentData.timestamp).toLocaleTimeString()}
          </p>
        </div>
      </div>
    </div>
  );
}

function DataCard({ icon, title, value, unit }) {
  return (
    <div className="bg-white p-6 rounded-xl shadow-md">
      <div className="flex items-center gap-3 mb-4">
        {icon}
        <h3 className="text-lg font-semibold">{title}</h3>
      </div>
      <p className="text-2xl font-bold">
        {value} {unit && <span className="text-sm text-gray-500">{unit}</span>}
      </p>
    </div>
  );
}