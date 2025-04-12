const express = require('express');
const router = express.Router();
const { check, validationResult } = require('express-validator');
const auth = require('../middleware/auth');

const Keyword = require('../models/Keyword');
const User = require('../models/User');

// @route   GET api/keywords
// @desc    Get all keywords
// @access  Private
router.get('/', auth, async (req, res) => {
  try {
    const keywords = await Keyword.find()
      .populate('creator', ['name', 'email'])
      .populate('domains', ['name'])
      .populate('tags', ['name', 'color'])
      .sort({ createdAt: -1 });
    
    res.json(keywords);
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

// @route   GET api/keywords/user
// @desc    Get user's keywords
// @access  Private
router.get('/user', auth, async (req, res) => {
  try {
    const keywords = await Keyword.find({ creator: req.user.id })
      .populate('domains', ['name'])
      .populate('tags', ['name', 'color'])
      .sort({ createdAt: -1 });
    
    res.json(keywords);
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

// @route   GET api/keywords/search
// @desc    Search keywords
// @access  Private
router.get('/search', auth, async (req, res) => {
  try {
    const { query } = req.query;
    
    if (!query) {
      return res.status(400).json({ msg: 'Search query is required' });
    }
    
    const keywords = await Keyword.find({ 
      $text: { $search: query } 
    })
      .populate('creator', ['name', 'email'])
      .populate('domains', ['name'])
      .populate('tags', ['name', 'color'])
      .sort({ score: { $meta: 'textScore' } });
    
    res.json(keywords);
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

// @route   POST api/keywords
// @desc    Create a keyword
// @access  Private
router.post(
  '/',
  [
    auth,
    [
      check('text', 'Keyword text is required').not().isEmpty(),
      check('description', 'Description is required').not().isEmpty()
    ]
  ],
  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    try {
      const { text, description, domains, tags, status } = req.body;

      // Check if keyword already exists
      const existingKeyword = await Keyword.findOne({ text });
      
      if (existingKeyword) {
        return res.status(400).json({ 
          msg: 'This keyword already exists',
          existingKeyword
        });
      }

      const newKeyword = new Keyword({
        text,
        description,
        creator: req.user.id,
        domains,
        tags,
        status: status || 'draft'
      });

      const keyword = await newKeyword.save();
      
      // Populate the saved keyword with related data
      const populatedKeyword = await Keyword.findById(keyword._id)
        .populate('creator', ['name', 'email'])
        .populate('domains', ['name'])
        .populate('tags', ['name', 'color']);

      res.json(populatedKeyword);
    } catch (err) {
      console.error(err.message);
      res.status(500).send('Server Error');
    }
  }
);

// @route   PUT api/keywords/:id
// @desc    Update a keyword
// @access  Private
router.put('/:id', auth, async (req, res) => {
  try {
    const { text, description, domains, tags, status } = req.body;

    // Build keyword object
    const keywordFields = {};
    if (text) keywordFields.text = text;
    if (description) keywordFields.description = description;
    if (domains) keywordFields.domains = domains;
    if (tags) keywordFields.tags = tags;
    if (status) keywordFields.status = status;
    keywordFields.updatedAt = Date.now();

    let keyword = await Keyword.findById(req.params.id);

    if (!keyword) {
      return res.status(404).json({ msg: 'Keyword not found' });
    }

    // Check if user is authorized to update
    if (keyword.creator.toString() !== req.user.id && req.user.role !== 'admin') {
      return res.status(401).json({ msg: 'Not authorized' });
    }

    // If text is being changed, check if it already exists
    if (text && text !== keyword.text) {
      const existingKeyword = await Keyword.findOne({ text });
      
      if (existingKeyword) {
        return res.status(400).json({ 
          msg: 'This keyword already exists',
          existingKeyword
        });
      }
    }

    keyword = await Keyword.findByIdAndUpdate(
      req.params.id,
      { $set: keywordFields },
      { new: true }
    )
      .populate('creator', ['name', 'email'])
      .populate('domains', ['name'])
      .populate('tags', ['name', 'color']);

    res.json(keyword);
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

// @route   DELETE api/keywords/:id
// @desc    Delete a keyword
// @access  Private
router.delete('/:id', auth, async (req, res) => {
  try {
    const keyword = await Keyword.findById(req.params.id);

    if (!keyword) {
      return res.status(404).json({ msg: 'Keyword not found' });
    }

    // Check if user is authorized to delete
    if (keyword.creator.toString() !== req.user.id && req.user.role !== 'admin') {
      return res.status(401).json({ msg: 'Not authorized' });
    }

    await keyword.remove();

    res.json({ msg: 'Keyword removed' });
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

module.exports = router;