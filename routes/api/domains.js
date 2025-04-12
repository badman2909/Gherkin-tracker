const express = require('express');
const router = express.Router();
const { check, validationResult } = require('express-validator');
const auth = require('../../middleware/auth');

const Domain = require('../../models/Domain');
const User = require('../../models/User');

// @route    POST api/domains
// @desc     Create a domain
// @access   Private
router.post(
  '/',
  [
    auth,
    [
      check('name', 'Name is required').not().isEmpty()
    ]
  ],
  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    try {
      const user = await User.findById(req.user.id).select('-password');

      const newDomain = new Domain({
        name: req.body.name,
        description: req.body.description,
        user: req.user.id
      });

      const domain = await newDomain.save();

      res.json(domain);
    } catch (err) {
      console.error(err.message);
      res.status(500).send('Server Error');
    }
  }
);

// @route    GET api/domains
// @desc     Get all domains
// @access   Private
router.get('/', auth, async (req, res) => {
  try {
    const domains = await Domain.find().sort({ date: -1 });
    res.json(domains);
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

// @route    GET api/domains/:id
// @desc     Get domain by ID
// @access   Private
router.get('/:id', auth, async (req, res) => {
  try {
    const domain = await Domain.findById(req.params.id);

    if (!domain) {
      return res.status(404).json({ msg: 'Domain not found' });
    }

    res.json(domain);
  } catch (err) {
    console.error(err.message);
    if (err.kind === 'ObjectId') {
      return res.status(404).json({ msg: 'Domain not found' });
    }
    res.status(500).send('Server Error');
  }
});

// @route    DELETE api/domains/:id
// @desc     Delete a domain
// @access   Private
router.delete('/:id', auth, async (req, res) => {
  try {
    const domain = await Domain.findById(req.params.id);

    if (!domain) {
      return res.status(404).json({ msg: 'Domain not found' });
    }

    // Check user
    if (domain.user.toString() !== req.user.id) {
      return res.status(401).json({ msg: 'User not authorized' });
    }

    await domain.remove();

    res.json({ msg: 'Domain removed' });
  } catch (err) {
    console.error(err.message);
    if (err.kind === 'ObjectId') {
      return res.status(404).json({ msg: 'Domain not found' });
    }
    res.status(500).send('Server Error');
  }
});

// @route    PUT api/domains/:id
// @desc     Update a domain
// @access   Private
router.put('/:id', auth, async (req, res) => {
  try {
    const domain = await Domain.findById(req.params.id);

    if (!domain) {
      return res.status(404).json({ msg: 'Domain not found' });
    }

    // Check user
    if (domain.user.toString() !== req.user.id) {
      return res.status(401).json({ msg: 'User not authorized' });
    }

    // Update fields
    if (req.body.name) domain.name = req.body.name;
    if (req.body.description) domain.description = req.body.description;

    await domain.save();

    res.json(domain);
  } catch (err) {
    console.error(err.message);
    if (err.kind === 'ObjectId') {
      return res.status(404).json({ msg: 'Domain not found' });
    }
    res.status(500).send('Server Error');
  }
});

module.exports = router;