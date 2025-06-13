import { useEffect, useState, useRef } from 'react';
import { Sun, DollarSign, Activity, Battery } from 'lucide-react';
import { Chart, LineController, LineElement, PointElement, LinearScale, CategoryScale } from 'chart.js';
import Navbar from './Navbar';

Chart.register(LineController, LineElement, PointElement, LinearScale, CategoryScale);

export default function Data() {
  const [currentData, setCurrentData] = useState(null);
  const [picoData, setPicoData] = useState({}); 
  const [loading, setLoading] = useState(true);
  const [wsStatus, setWsStatus] = useState('disconnected');
  const chartRef = useRef(null);

  const moneyTotalsRef = useRef({
    pico_blue: 0,
    pico_red: 0,
    pico_red2: 0,
    pico_yellow: 0
  });
  const [moneyTotals, setMoneyTotals] = useState({
    pico_blue: 0,
    pico_red: 0,
    pico_red2: 0,
    pico_yellow: 0
  });

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
          // Update individual Pico data
          setPicoData(prev => ({
            ...prev,
            [newData.picoName]: newData
          }));

          // Update running total for this Pico
          if (newData.picoName && moneyTotalsRef.current[newData.picoName] !== undefined) {
            const moneyValue = newData.money ?? 0;
            moneyTotalsRef.current[newData.picoName] += moneyValue;
            setMoneyTotals({...moneyTotalsRef.current});
          }
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

  if (loading) return <div className="p-8">Loading initial data...</div>;
  if (!currentData) return <div className="p-8">No data available</div>;

  const totalDeferrableEnergy = (currentData.deferrable || []).reduce(
    (sum, device) => sum + (device.energy || 0), 0
  );

  return (
    <>
      <Navbar />
      <div className="min-h-screen bg-gray-50 p-8">
        <h1 className="text-3xl font-bold mb-8">Smart Grid Dashboard</h1>
        <div className="mb-4 text-sm text-gray-600">
          WebSocket status: {wsStatus} | Last tick: {currentData.tick}
        </div>

        <div className="flex gap-2 mb-6">
          <button 
            className='text-white bg-gradient-to-r from-teal-400 via-teal-500 to-teal-600 hover:bg-gradient-to-br hover:scale-105 focus:ring-4 focus:outline-none focus:ring-teal-300 dark:focus:ring-teal-800 shadow-lg shadow-teal-500/50 dark:shadow-lg dark:shadow-teal-800/80 font-medium rounded-lg text-sm px-5 py-2.5 text-center me-2 mb-2'
            onClick={async () => {
              try {
                const response = await fetch('http://localhost:3000/set-mode', {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({ mode: 'mppt' }),
                });
                const data = await response.json();
                console.log(data.message);
              } catch (error) {
                console.error('Error setting MPPT mode:', error);
              }
            }}
          >
            MPPT Mode
          </button>

          <button 
            className='text-white bg-gradient-to-r from-red-400 via-red-500 to-red-600 hover:bg-gradient-to-br hover:scale-105 focus:ring-4 focus:outline-none focus:ring-red-300 dark:focus:ring-red-800 shadow-lg shadow-red-500/50 dark:shadow-lg dark:shadow-red-800/80 font-medium rounded-lg text-sm px-5 py-2.5 text-center me-2 mb-2'
            onClick={async () => {
              try {
                const response = await fetch('http://localhost:3000/set-mode', {
                  method: 'POST',
                  headers: {
                    'Content-Type': 'application/json',
                  },
                  body: JSON.stringify({ mode: 'normal' }),
                });
                const data = await response.json();
                console.log(data.message);
              } catch (error) {
                console.error('Error setting normal mode:', error);
              }
            }}
          >
            Normal Mode
          </button>
        </div>

        {/* Pico Data Display */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          {Object.entries(picoData).map(([picoName, data]) => (
            <div key={picoName} className="bg-white p-6 rounded-xl shadow-md">
              <h2 className="text-xl font-semibold mb-4 capitalize">{picoName.replace('_', ' ')} Data</h2>
              <div className="grid grid-cols-2 gap-4 text-lg">
                <div><strong>Tick:</strong> {data.tick}</div>
                <div><strong>Vin:</strong> {data.Vin}</div>
                <div><strong>Vout:</strong> {data.Vout}</div>
                <div><strong>Iout:</strong> {data.Iout}</div>
                <div><strong>Power:</strong> {(data.power ?? 0).toFixed(3)} W</div>
                <div><strong>Latest Money:</strong> ${(data.money ?? 0).toFixed(2)}</div>
                <div><strong>Total Money:</strong> ${moneyTotals[picoName]?.toFixed(2) || '0.00'}</div>
                <div><strong>Timestamp:</strong> {new Date(data.timestamp).toLocaleString()}</div>
              </div>
            </div>
          ))}
        </div>
        
      </div>
    </>
  );
}