import { useEffect, useState, useRef } from 'react';
import { Sun, DollarSign, Activity, Battery } from 'lucide-react';
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale } from 'chart.js';

// Register Chart.js components
Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale);

export default function App() {
  const [currentData, setCurrentData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [wsStatus, setWsStatus] = useState('disconnected');
  const chartRef = useRef(null);

  useEffect(() => {
    const fetchLatest = async () => {
      try {
        const res = await fetch('http://localhost:3000/latest');
        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
        const data = await res.json();
        setCurrentData(data);
        setLoading(false);
      } catch (error) {
        console.error('Fetch error:', error);
        setLoading(false);
      }
    };

    fetchLatest();

    const ws = new WebSocket('ws://localhost:3000');
    
    ws.onopen = () => {
      console.log("WebSocket connected");
      setWsStatus('connected');
    };
    
    ws.onmessage = (event) => {
      try {
        const newData = JSON.parse(event.data);
        setCurrentData(newData);
      } catch (e) {
        console.error("WS parse error:", e);
      }
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      setWsStatus('error');
    };

    ws.onclose = () => {
      console.log("WebSocket disconnected");
      setWsStatus('disconnected');
    };

    return () => ws.close();
  }, []);

  useEffect(() => {
    if (!currentData?.yesterday) return;

    // Prepare chart data
    const labels = currentData.yesterday.map((_, index) => `Tick ${index}`);
    const buyPrices = currentData.yesterday.map(item => item.buy_price);
    const sellPrices = currentData.yesterday.map(item => item.sell_price);

    const ctx = document.getElementById('priceChart').getContext('2d');

    // Destroy previous chart if it exists
    if (chartRef.current) {
      chartRef.current.destroy();
    }

    chartRef.current = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          {
            label: 'Buy Price',
            data: buyPrices,
            borderColor: 'rgb(75, 192, 192)',
            tension: 0.1
          },
          {
            label: 'Sell Price',
            data: sellPrices,
            borderColor: 'rgb(255, 99, 132)',
            tension: 0.1
          }
        ]
      },
      options: {
        responsive: true,
        plugins: {
          title: {
            display: true,
            text: 'Yesterday\'s Prices'
          },
        },
        scales: {
          y: {
            beginAtZero: true,
            title: {
              display: true,
              text: 'Price ($)'
            }
          },
          x: {
            title: {
              display: true,
              text: 'Time (Tick)'
            }
          }
        }
      }
    });

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
      }
    };
  }, [currentData]);

  if (loading) return <div className="p-8">Loading initial data...</div>;
  if (!currentData) return <div className="p-8">No data available</div>;

  // Calculate deferrable load summary
  const totalDeferrableEnergy = currentData.deferrable.reduce(
    (sum, device) => sum + device.energy, 0
  );

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-3xl font-bold mb-8">Smart Grid Dashboard</h1>
      <div className="mb-4 text-sm text-gray-600">
        WebSocket status: {wsStatus} | Last tick: {currentData.tick}
      </div>

      {/* Price History Chart - Moved up */}
      <div className="bg-white p-6 rounded-xl shadow-md mb-8">
        <h2 className="text-xl font-semibold mb-4">Yesterday's Price History</h2>
        <div className="h-96">
          <canvas id="priceChart"></canvas>
        </div>
      </div>
      
      {/* Data Cards - Now appears below the chart */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
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
        <DataCard
          icon={<Battery className="text-orange-500" />}
          title="Deferrable Load"
          value={totalDeferrableEnergy.toFixed(2)}
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