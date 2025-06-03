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
        type: Map,
        of: Number,
        required: true
    },
    prices: {
        type: Map,
        of: Number,
        required: true
    },
    demand: {
        type: Map,
        of: Number,
        required: true
    },
    deferrable: {
        type: Array,
        required: true
    },
    yesterday: {
        type: Array,
        required: true
    }
});

const Job = mongoose.model('Job', schema, 'combined_ticks');
export default Job;