import mongoose from 'mongoose';

const schema = mongoose.Schema({
    tick: {
        type: Number,
        required: true
    },
    timestamp: {
        type: Date,
        required: true
    },
    sun: {
        type: Number,
        required: true
    },
    price: {
        buy: {
            type: Number,
            required: true
        },
        sell: {
            type: Number,
            required: true
        },
        day: {
            type: Number,
            required: true
        }
    },
    demand: {
        type: Number,
        required: true
    }
});


const Job = mongoose.model('Job', schema, 'combined_ticks');
export default Job;