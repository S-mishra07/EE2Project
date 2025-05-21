import express from 'express';
import cors from 'cors';
import mongoose from 'mongoose';
import { mongodburl } from './config.js';
import job from "./models/jobmodel.js";

const app = express();


app.use(cors());
app.use(express.json());

app.get("/find", async (req, res) => {
    try {
        const jobs = await job.find({});
        res.status(200).json({ success: true, data: jobs });
    } catch (error) {
        console.error(error);
        res.status(500).json({ success: false, error: error.message });
    }
});

app.delete("/find/:id", async (req, res) => {
    const { id } = req.params;

    try {
        await job.findByIdAndDelete(id);
        return res.status(200).json({ success: true, message: "Your job profile has been deleted" });
    } catch (error) {
        return res.status(500).json({ success: false, message: "Your job profile has not been deleted" });
    }
});

app.post("/find", async (req, res) => {
    const jobData = req.body;

    if (!jobData.Energy_in || !jobData.Energy_out || !jobData.Economics || !jobData.Internal_variables) {
        return res.status(404).json({ success: false, message: "You have not entered all the fields" });
    }

    const newjob = new job(jobData);

    try { 
        await newjob.save();
        return res.status(200).json({ success: true, message: "You have updated your job listing" });
    }
    catch (error) {
        return res.status(404).json({ success: false, message: "There has been an issue" }); 
    }
});

mongoose.connect(mongodburl)
  .then(() => {
    console.log("Connected to MongoDB");
    app.listen(3000, () => {
      console.log("Server running on port 3000");
    });
  })
  .catch(error => {
    console.error("Database connection error:", error);
    process.exit(1);
  });
export default app;