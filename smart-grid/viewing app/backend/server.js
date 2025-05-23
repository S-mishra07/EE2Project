import express from 'express';
import mongoose from 'mongoose';
import cors from 'cors';
import { mongodburl } from './config.js';
import Job from './models/jobmodel.js';

const app = express();
app.use(cors());


import { WebSocketServer } from 'ws';
const server = app.listen(3000, () => console.log('Server running on port 3000'));
const wss = new WebSocketServer({ server });


let changeStream;
mongoose.connect(mongodburl)
  .then(() => {
    console.log('Connected to MongoDB');
    const collection = mongoose.connection.db.collection('combined_ticks');
    changeStream = collection.watch([], { fullDocument: 'updateLookup' });
    
    changeStream.on('change', (change) => {
      if (change.operationType === 'insert') {
        const newData = change.fullDocument;
        wss.clients.forEach(client => {
          if (client.readyState === 1) { // 1 = OPEN
            client.send(JSON.stringify(newData));
          }
        });
      }
    });
  });


app.get('/latest', async (req, res) => {
  try {
    const latest = await Job.findOne().sort({ $natural: -1 });
    res.json(latest || null);
  } catch (error) {
    res.status(500).json({ error: error.message });
  }
});