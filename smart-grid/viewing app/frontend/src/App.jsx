import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Data from './components/Data';
import Pico from './components/Pico';
import Capacitor from './components/Capacitor'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={< Data />} />
        <Route path="/picos" element={< Pico />} />
        <Route path="/capacitor" element={<Capacitor />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;