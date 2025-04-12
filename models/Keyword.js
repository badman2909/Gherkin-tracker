const mongoose = require('mongoose');
const Schema = mongoose.Schema;

const KeywordSchema = new Schema({
  user: {
    type: Schema.Types.ObjectId,
    ref: 'users'
  },
  text: {
    type: String,
    required: true
  },
  type: {
    type: String,
    required: true,
    enum: ['Given', 'When', 'Then', 'And', 'But']
  },
  domain: {
    type: String,
    required: true
  },
  tags: {
    type: [String]
  },
  date: {
    type: Date,
    default: Date.now
  }
});

module.exports = Keyword = mongoose.model('keyword', KeywordSchema);