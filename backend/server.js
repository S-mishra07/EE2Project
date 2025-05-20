import express from 'express';
import cors from 'cors'; // ✅ Added CORS middleware
import { mongodburl } from './config.js';
import job from "./models/jobmodel.js";
import mongoose from 'mongoose';

const app = express();

// Middleware
app.use(cors()); // ✅ Allow cross-origin requests
app.use(express.json()); // To parse JSON request bodies

// Routes

// Get all jobs
app.get("/find", async (req, res) => {
    try {
        const jobs = await job.find({});
        res.status(200).json({
            success: true,
            message: "Your current live jobs are these:",
            jobs
        });
    } catch (error) {
        console.error("Error fetching jobs:", error); // ✅ Better logging
        res.status(500).json({ success: false, message: "Your jobs cannot be fetched currently" });
    }
});

// Update a job by ID
app.put("/find/:id", async (req, res) => {
    const { id } = req.params;
    const jobUpdate = req.body;

    try {
        const updatedJob = await job.findByIdAndUpdate(id, jobUpdate, { new: true });
        if (!updatedJob) {
            return res.status(404).json({ success: false, message: "Job not found" });
        }
        res.status(200).json({ success: true, message: "Job updated successfully", job: updatedJob });
    } catch (error) {
        console.error("Error updating job:", error);
        res.status(500).json({ success: false, message: "There has been an error" });
    }
});

// Create a new job
app.post("/find", async (req, res) => {
    const jobData = req.body;

    const requiredFields = ['position_title', 'company_title', 'curr_status', 'location'];
    const missingFields = requiredFields.filter(field => !jobData[field]);

    if (missingFields.length > 0) {
        return res.status(400).json({
            success: false,
            message: `Missing required fields: ${missingFields.join(', ')}`,
        });
    }

    const newJob = new job(jobData);

    try {
        await newJob.save();
        res.status(201).json({ success: true, message: "New job added successfully", job: newJob });
    } catch (error) {
        console.error("Error saving job:", error);
        res.status(500).json({ success: false, message: "There has been an issue" });
    }
});

// Delete a job by ID
app.delete("/find/:id", async (req, res) => {
    const { id } = req.params;

    try {
        const deletedJob = await job.findByIdAndDelete(id);
        if (!deletedJob) {
            return res.status(404).json({ success: false, message: "Job not found" });
        }
        res.status(200).json({ success: true, message: "Job deleted successfully" });
    } catch (error) {
        console.error("Error deleting job:", error);
        res.status(500).json({ success: false, message: "Failed to delete job" });
    }
});

// Start server
mongoose
    .connect(mongodburl)
    .then(() => {
        console.log("✅ Successfully connected to MongoDB");
        const PORT = 4000;
        app.listen(PORT, () => {
            console.log(`🚀 Server is running on http://localhost:${PORT}`);
        });
    })
    .catch((error) => {
        console.error("❌ Error connecting to MongoDB:", error.message);
    });

export default app; // ✅ Useful for testing or deploying as a module