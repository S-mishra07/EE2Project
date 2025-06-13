import express from 'express';
import mongoose from 'mongoose';
import cors from 'cors';
import { mongodburl } from './config.js';
import Job from './models/jobmodel.js';
import { WebSocketServer } from 'ws';

const app = express();
app.use(cors());
app.use(express.json());

const server = app.listen(3000, () => console.log('Server running on port 3000'));
const wss = new WebSocketServer({ server });

let changeStreamCombinedTicks;
let changeStreamPicoMessages;
let changeStreamMode;

// Track last tick values for each collection
let lastCombinedTicksTick = null;
let lastPicoMessagesTick = null;

async function startChangeStreams() {
  await mongoose.connect(mongodburl);
  console.log('Connected to MongoDB');

  // Combined ticks change stream
  const combinedTicksCollection = mongoose.connection.client.db('test').collection('combined_ticks');
  changeStreamCombinedTicks = combinedTicksCollection.watch([], { fullDocument: 'updateLookup' });

  changeStreamCombinedTicks.on('change', (change) => {
    if (change.operationType === 'insert') {
      const newData = change.fullDocument;

      // Skip if tick hasn't changed
      if (lastCombinedTicksTick !== null && newData.tick === lastCombinedTicksTick) {
        console.log(`Skipping combined_ticks update - same tick (${newData.tick})`);
        return;
      }
      
      lastCombinedTicksTick = newData.tick;

      const transformedData = {
        type: 'combined_ticks',
        tick: newData.tick,
        timestamp: newData.timestamp || Date.now(),
        sun: newData.sun?.sun ?? 0,
        price: {
          buy: newData.prices?.buy_price ?? 0,
          sell: newData.prices?.sell_price ?? 0,
          day: newData.prices?.day ?? 0
        },
        demand: newData.demand?.demand ?? 0,
        deferrable: Array.isArray(newData.deferrable) ? newData.deferrable : [],
        yesterday: Array.isArray(newData.yesterday) ? newData.yesterday : []
      };

      broadcastToClients(transformedData);
    }
  });

  changeStreamCombinedTicks.on('error', (err) => {
    console.error('Change stream combined_ticks error:', err);
  });

  // Pico messages change stream
  const picoMessagesCollection = mongoose.connection.client.db('test_pico').collection('pico_messages');
  changeStreamPicoMessages = picoMessagesCollection.watch([], { fullDocument: 'updateLookup' });

  changeStreamPicoMessages.on('change', (change) => {
    if (change.operationType === 'insert') {
      const newData = change.fullDocument;

      // Skip if tick hasn't changed
      if (lastPicoMessagesTick !== null && newData.tick === lastPicoMessagesTick) {
        console.log(`Skipping pico_messages update - same tick (${newData.tick})`);
        return;
      }
      
      lastPicoMessagesTick = newData.tick;

      const transformedData = {
        type: 'pico_messages',
        tick: newData.tick ?? 0,
        Vin: newData.Vin ?? '-',
        Vout: newData.Vout ?? '-',
        Iout: newData.Iout ?? '-',
        power: newData.power ?? 0,
        money: newData.money ?? 0,
        timestamp: newData.timestamp || Date.now()
      };

      broadcastToClients(transformedData);
    }
  });

  changeStreamPicoMessages.on('error', (err) => {
    console.error('Change stream pico_messages error:', err);
  });

  // Mode change stream
  const modeCollection = mongoose.connection.client.db('test_pico').collection('mode');
  changeStreamMode = modeCollection.watch([], { fullDocument: 'updateLookup' });

  changeStreamMode.on('change', (change) => {
    if (change.operationType === 'insert') {
      const newData = change.fullDocument;
      const transformedData = {
        type: 'mode_change',
        mode: newData.mode,
        timestamp: newData.timestamp || Date.now()
      };
      broadcastToClients(transformedData);
    }
  });

  changeStreamMode.on('error', (err) => {
    console.error('Change stream mode error:', err);
  });
}

function broadcastToClients(data) {
  wss.clients.forEach(client => {
    if (client.readyState === 1) {
      client.send(JSON.stringify(data));
    }
  });
}

// New endpoint to handle mode selection
app.post('/set-mode', async (req, res) => {
  try {
    const { mode } = req.body;
    
    if (!mode || (mode !== 'mppt' && mode !== 'normal')) {
      return res.status(400).json({ error: 'Invalid mode. Must be "mppt" or "normal"' });
    }

    const modeCollection = mongoose.connection.client.db('test_pico').collection('mode');
    await modeCollection.insertOne({
      mode,
      timestamp: Date.now()
    });

    res.status(200).json({ message: `Mode set to ${mode}` });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// New endpoint to get current mode
app.get('/current-mode', async (req, res) => {
  try {
    const modeCollection = mongoose.connection.client.db('test_pico').collection('mode');
    const currentMode = await modeCollection.findOne({}, { sort: { $natural: -1 } });
    
    res.status(200).json(currentMode || { mode: 'not_set' });
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

// Existing endpoints
app.get('/latest', async (req, res) => {
  try {
    const latest = await Job.findOne().sort({ $natural: -1 });
    if (!latest) return res.status(404).json({ message: 'No data found' });

    const transformedData = {
      tick: latest.tick,
      timestamp: latest.timestamp || Date.now(),
      sun: latest.sun?.sun ?? 0,
      price: {
        buy: latest.prices?.buy_price ?? 0,
        sell: latest.prices?.sell_price ?? 0,
        day: latest.prices?.day ?? 0
      },
      demand: latest.demand?.demand ?? 0,
      deferrable: Array.isArray(latest.deferrable) ? latest.deferrable : [],
      yesterday: Array.isArray(latest.yesterday) ? latest.yesterday : []
    };

    res.json(transformedData);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});

wss.on('connection', (ws) => {
  console.log('New WebSocket connection');

  ws.on('error', (err) => {
    console.error('WebSocket error:', err);
  });

  ws.on('close', () => {
    console.log('WebSocket disconnected');
  });
});

startChangeStreams().catch(console.error);