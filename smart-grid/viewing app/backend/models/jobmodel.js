import mongoose from 'mongoose'; 

const schema = mongoose.Schema({


    Energy_in: {
        type: String,
        required : true,
    },
    Energy_out: {
        type: String,
        required : true,
    },
    Economics : {
        type: String,
        required : true,

    },
    Internal_variables : {
        type : String,
        required : true,

    }


}); 


const job = mongoose.model('Job', schema); 
export default job;
