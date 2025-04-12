const express = require('express');
const router = express.Router();
const { check, validationResult } = require('express-validator');
const auth = require('../middleware/auth');

const Domain = require('../models/Domain');

// @route   GET api/domains
// @desc    Get all domains
// @access  Private
router.get('/', auth, async (req, res) => {
  try {
    const domains = await Domain.find().sort({ name: 1 });
    res.json(domains);
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

// @route   POST api/domains
// @desc    Create a domain
// @access  Private/Admin
router.post(
  '/',
  [
    auth,
    [
      check('name', 'Domain name is required').not().isEmpty()
    ]
  ],
  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    try {
      // Check if user is admin
      if (req.user.role !== 'admin') {
        return res.status(403).json({ msg: 'Not authorized' });
      }

      const { name, description } = req.body;

      // Check if domain already exists
      const existingDomain = await Domain.findOne({ name });
      
      if (existingDomain) {
        return res.status(400).json({ msg: 'Domain already exists' });
      }

      const newDomain = new Domain({
        name,
        description
      });

      const domain = await newDomain.save();

      res.json(domain);
    } catch (err) {
      console.error(err.message);
      res.status(500).send('Server Error');
    }
  }
);

// @route   PUT api/domains/:id
// @desc    Update a domain
// @access  Private/Admin
router.put('/:id', auth, async (req, res) => {
  try {
    // Check if user is admin
    if (req.user.role !== 'admin') {
      return res.status(403).json({ msg: 'Not authorized' });
    }

    const { name, description } = req.body;

    // Build domain object
    const domainFields = {};
    if (name) domainFields.name = name;
    if (description) domainFields.description = description;

    let domain = await Domain.findById(req.params.id);

    if (!domain) {
      return res.status(404).json({ msg: 'Domain not found' });
    }

    // If name is being changed, check if it already exists
    if (name && name !== domain.name) {
      const existingDomain = await Domain.findOne({ name });
      
      if (existingDomain) {
        return res.status(400).json({ msg: 'Domain name already exists' });
      }
    }

    domain = await Domain.findByIdAndUpdate(
      req.params.id,
      { $set: domainFields },
      { new: true }
    );

    res.json(domain);
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

// @route   DELETE api/domains/:id
// @desc    Delete a domain
// @access  Private/Admin
router.delete('/:id', auth, async (req, res) => {
  try {
    // Check if user is admin
    if (req.user.role !== 'admin') {
      return res.status(403).json({ msg: 'Not authorized' });
    }

    const domain = await Domain.findById(req.params.id);

    if (!domain) {
      return res.status(404).json({ msg: 'Domain not found' });
    }

    await domain.remove();

    res.json({ msg: 'Domain removed' });
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

module.exports = router;