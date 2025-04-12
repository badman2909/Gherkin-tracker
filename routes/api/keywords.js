const express = require('express');
const router = express.Router();
const { check, validationResult } = require('express-validator');
const auth = require('../../middleware/auth');

const Keyword = require('../../models/Keyword');
const User = require('../../models/User');

// @route    POST api/keywords
// @desc     Create a keyword
// @access   Private
router.post(
  '/',
  [
    auth,
    [
      check('text', 'Text is required').not().isEmpty(),
      check('type', 'Type is required').not().isEmpty(),
      check('domain', 'Domain is required').not().isEmpty()
    ]
  ],
  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    try {
      const user = await User.findById(req.user.id).select('-password');

      const newKeyword = new Keyword({
        text: req.body.text,
        type: req.body.type,
        domain: req.body.domain,
        tags: req.body.tags,
        user: req.user.id
      });

      const keyword = await newKeyword.save();

      res.json(keyword);
    } catch (err) {
      console.error(err.message);
      res.status(500).send('Server Error');
    }
  }
);

// @route    GET api/keywords
// @desc     Get all keywords
// @access   Private
router.get('/', auth, async (req, res) => {
  try {
    const keywords = await Keyword.find({ user: req.user.id }).sort({ date: -1 });
    res.json(keywords);
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

// @route    GET api/keywords/:id
// @desc     Get keyword by ID
// @access   Private
router.get('/:id', auth, async (req, res) => {
  try {
    const keyword = await Keyword.findById(req.params.id);

    if (!keyword) {
      return res.status(404).json({ msg: 'Keyword not found' });
    }

    // Check user
    if (keyword.user.toString() !== req.user.id) {
      return res.status(401).json({ msg: 'User not authorized' });
    }

    res.json(keyword);
  } catch (err) {
    console.error(err.message);
    if (err.kind === 'ObjectId') {
      return res.status(404).json({ msg: 'Keyword not found' });
    }
    res.status(500).send('Server Error');
  }
});

// @route    DELETE api/keywords/:id
// @desc     Delete a keyword
// @access   Private
router.delete('/:id', auth, async (req, res) => {
  try {
    const keyword = await Keyword.findById(req.params.id);

    if (!keyword) {
      return res.status(404).json({ msg: 'Keyword not found' });
    }

    // Check user
    if (keyword.user.toString() !== req.user.id) {
      return res.status(401).json({ msg: 'User not authorized' });
    }

    await keyword.remove();

    res.json({ msg: 'Keyword removed' });
  } catch (err) {
    console.error(err.message);
    if (err.kind === 'ObjectId') {
      return res.status(404).json({ msg: 'Keyword not found' });
    }
    res.status(500).send('Server Error');
  }
});

// @route    PUT api/keywords/:id
// @desc     Update a keyword
// @access   Private
router.put('/:id', auth, async (req, res) => {
  try {
    const keyword = await Keyword.findById(req.params.id);

    if (!keyword) {
      return res.status(404).json({ msg: 'Keyword not found' });
    }

    // Check user
    if (keyword.user.toString() !== req.user.id) {
      return res.status(401).json({ msg: 'User not authorized' });
    }

    // Update fields
    if (req.body.text) keyword.text = req.body.text;
    if (req.body.type) keyword.type = req.body.type;
    if (req.body.domain) keyword.domain = req.body.domain;
    if (req.body.tags) keyword.tags = req.body.tags;

    await keyword.save();

    res.json(keyword);
  } catch (err) {
    console.error(err.message);
    if (err.kind === 'ObjectId') {
      return res.status(404).json({ msg: 'Keyword not found' });
    }
    res.status(500).send('Server Error');
  }
});

module.exports = router;