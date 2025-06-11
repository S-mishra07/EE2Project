import { useEffect, useState, useRef } from 'react';
import { Sun, DollarSign, Activity, Battery } from 'lucide-react';
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale } from 'chart.js';

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale);

export default function App() {
  const [currentData, setCurrentData] = useState(null);
  const [picoData, setPicoData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [wsStatus, setWsStatus] = useState('disconnected');
  const chartRef = useRef(null);

  const moneyTotalRef = useRef(0); // running total
  const [moneyTotal, setMoneyTotal] = useState(0); // display value

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
        console.log('WS message received:', newData);
        if (newData.type === 'combined_ticks') {
          setCurrentData(newData);
        } else if (newData.type === 'pico_messages') {
          setPicoData(newData);

          // Update running total:
          const moneyValue = newData.money ?? 0;
          moneyTotalRef.current += moneyValue;
          setMoneyTotal(moneyTotalRef.current);
        }
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

    return () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    if (!currentData?.yesterday) return;

    const canvas = document.getElementById('priceChart');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');

    if (chartRef.current) {
      chartRef.current.destroy();
    }

    const labels = currentData.yesterday.map((_, index) => `Tick ${index}`);
    const buyPrices = currentData.yesterday.map(item => item.buy_price ?? 0);
    const sellPrices = currentData.yesterday.map(item => item.sell_price ?? 0);

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
            text: "Yesterday's Prices"
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

  const totalDeferrableEnergy = (currentData.deferrable || []).reduce(
    (sum, device) => sum + (device.energy || 0), 0
  );

  return (
    <div className="min-h-screen bg-gray-50 p-8">
      <h1 className="text-3xl font-bold mb-8">Smart Grid Dashboard</h1>
      <div className="mb-4 text-sm text-gray-600">
        WebSocket status: {wsStatus} | Last tick: {currentData.tick}
      </div>

      <div className="bg-white p-6 rounded-xl shadow-md mb-8">
        <h2 className="text-xl font-semibold mb-4">Yesterday's Price History</h2>
        <div className="h-96">
          <canvas id="priceChart"></canvas>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
        <DataCard icon={<Sun className="text-yellow-500" />} title="Sunshine" value={currentData.sun} unit="%" />
        <DataCard icon={<DollarSign className="text-green-500" />} title="Buy Price" value={currentData.price?.buy} unit="$" />
        <DataCard icon={<DollarSign className="text-blue-500" />} title="Sell Price" value={currentData.price?.sell} unit="$" />
        <DataCard icon={<Activity className="text-purple-500" />} title="Demand" value={(currentData.demand ?? 0).toFixed(2)} unit="kW" />
        <DataCard icon={<Battery className="text-orange-500" />} title="Deferrable Load" value={totalDeferrableEnergy.toFixed(2)} unit="kW" />
        <div className="bg-white p-6 rounded-xl shadow-md">
          <h3 className="text-lg font-semibold mb-2">Current Tick</h3>
          <p className="text-2xl font-bold">{currentData.tick}</p>
          <p className="text-sm text-gray-500 mt-2">
            Updated: {new Date(currentData.timestamp).toLocaleTimeString()}
          </p>
        </div>
      </div>

      {picoData && (
        <div className="bg-white p-6 rounded-xl shadow-md">
          <h2 className="text-xl font-semibold mb-4">Pico Messages Data</h2>
          <div className="grid grid-cols-2 gap-4 text-lg">
            <div><strong>Tick:</strong> {picoData.tick}</div>
            <div><strong>Vin:</strong> {picoData.Vin}</div>
            <div><strong>Vout:</strong> {picoData.Vout}</div>
            <div><strong>Iout:</strong> {picoData.Iout}</div>
            <div><strong>Power:</strong> {(picoData.power ?? 0).toFixed(3)} W</div>
            <div><strong>Money (latest message):</strong> ${(picoData.money ?? 0).toFixed(2)}</div>
            <div><strong>Money (running total):</strong> ${moneyTotal.toFixed(2)}</div>
            <div><strong>Timestamp:</strong> {new Date(picoData.timestamp).toLocaleString()}</div>
          </div>
        </div>
      )}
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
        {value} {unit && <span className="text-sm font-normal">{unit}</span>}
      </p>
    </div>
  );
}
