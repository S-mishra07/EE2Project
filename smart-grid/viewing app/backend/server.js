import express from 'express';
import mongoose from 'mongoose';
import cors from 'cors';
import { mongodburl } from './config.js';
import Job from './models/jobmodel.js';

const app = express();
app.use(cors());
app.use(express.json());

import { WebSocketServer } from 'ws';
const server = app.listen(3000, () => console.log('Server running on port 3000'));
const wss = new WebSocketServer({ server });

// Initialize changeStream at the top level
let changeStream;

mongoose.connect(mongodburl)
  .then(() => {
    console.log('Connected to MongoDB');
    const collection = mongoose.connection.db.collection('combined_ticks');
    
    // Initialize changeStream here
    changeStream = collection.watch([], { fullDocument: 'updateLookup' });
    
    changeStream.on('change', (change) => {
      if (change.operationType === 'insert') {
        const newData = change.fullDocument;
        
        // Transform data for frontend
        const transformedData = {
          tick: newData.tick,
          timestamp: newData.timestamp,
          sun: newData.sun?.sun || 0,
          price: {
            buy: newData.prices?.buy_price || 0,
            sell: newData.prices?.sell_price || 0,
            day: newData.prices?.day || 0
          },
          demand: newData.demand?.demand || 0,
          deferrable: newData.deferrable || [],
          yesterday: newData.yesterday || []
        };

        wss.clients.forEach(client => {
          if (client.readyState === 1) {
            client.send(JSON.stringify(transformedData));
          }
        });
      }
    });

    changeStream.on('error', (err) => {
      console.error('Change stream error:', err);
    });
  })
  .catch(err => console.error('MongoDB connection error:', err));

app.get('/latest', async (req, res) => {
  try {
    const latest = await Job.findOne().sort({ $natural: -1 });
    
    if (!latest) {
      return res.status(404).json({ message: 'No data found' });
    }

    const transformedData = {
      tick: latest.tick,
      timestamp: latest.timestamp,
      sun: latest.sun?.sun || 0,
      price: {
        buy: latest.prices?.buy_price || 0,
        sell: latest.prices?.sell_price || 0,
        day: latest.prices?.day || 0
      },
      demand: latest.demand?.demand || 0,
      deferrable: latest.deferrable || [],
      yesterday: latest.yesterday || []
    };

    res.json(transformedData);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// WebSocket connection logging
wss.on('connection', (ws) => {
  console.log('New WebSocket connection');
  
  ws.on('error', (err) => {
    console.error('WebSocket error:', err);
  });
  
  ws.on('close', () => {
    console.log('WebSocket disconnected');
  });
});