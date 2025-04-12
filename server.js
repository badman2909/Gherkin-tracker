const express = require('express');
const connectDB = require('./config/db');
const path = require('path');

const app = express();

// Connect Database
connectDB();

// Init Middleware
app.use(express.json({ extended: false }));

// Define a simple route for the root path
app.get('/', (req, res) => {
  res.json({ msg: 'Welcome to the Gherkin Tracker API' });
});

// Define Routes
app.use('/api/users', require('./routes/api/users'));
app.use('/api/auth', require('./routes/api/auth'));
app.use('/api/keywords', require('./routes/api/keywords'));
app.use('/api/domains', require('./routes/api/domains'));
app.use('/api/templates', require('./routes/api/templates'));
app.use('/api/reports', require('./routes/api/reports'));
app.use('/api/validator', require('./routes/api/validator'));

// Serve static assets in production
if (process.env.NODE_ENV === 'production') {
  // Set static folder
  app.use(express.static('client/build'));

  app.get('*', (req, res) => {
    res.sendFile(path.resolve(__dirname, 'client', 'build', 'index.html'));
  });
}

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => console.log(`Server started on port ${PORT}`));