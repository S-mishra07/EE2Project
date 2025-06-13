import { useState } from 'react';
import { motion } from 'motion/react';
import { useNavigate } from 'react-router-dom';

const Navbar = () => {
  const isLoading = false;
  const navigate = useNavigate();

  return (
    <div className="flex flex-wrap gap-2 ml-1">
      <div className="p-2">
        <button
          type="button"
          disabled={isLoading}
          onClick={() => navigate(`/`)}
          className={`px-4 py-2 rounded-lg transition-all ${
            isLoading
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-teal-600 hover:bg-teal-700 text-white transform hover:scale-105'
          }`}
        >
          Current and Past Data
        </button>
      </div>

      <div className="p-2">
        <button
          type="button"
          disabled={isLoading}
          onClick={() => navigate(`/capacitor`)}
          className={`px-4 py-2 rounded-lg transition-all ${
            isLoading
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-blue-600 hover:bg-blue-700 text-white transform hover:scale-105'
          }`}
        >
          Capacitor Data
        </button>
      </div>

      <div className="p-2">
        <button
          type="button"
          disabled={isLoading}
          onClick={() => navigate(`/picos`)}
          className={`px-4 py-2 rounded-lg transition-all ${
            isLoading
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-purple-600 hover:bg-purple-700 text-white transform hover:scale-105'
          }`}
        >
          Pico Data
        </button>
      </div>
    </div>
  );
};

export default Navbar;
