const express = require('express');
const router = express.Router();
const { check, validationResult } = require('express-validator');
const auth = require('../middleware/auth');

const Tag = require('../models/Tag');

// @route   GET api/tags
// @desc    Get all tags
// @access  Private
router.get('/', auth, async (req, res) => {
  try {
    const tags = await Tag.find().sort({ name: 1 });
    res.json(tags);
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

// @route   POST api/tags
// @desc    Create a tag
// @access  Private
router.post(
  '/',
  [
    auth,
    [
      check('name', 'Tag name is required').not().isEmpty()
    ]
  ],
  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }

    try {
      const { name, color } = req.body;

      // Check if tag already exists
      const existingTag = await Tag.findOne({ name });
      
      if (existingTag) {
        return res.status(400).json({ msg: 'Tag already exists' });
      }

      const newTag = new Tag({
        name,
        color
      });

      const tag = await newTag.save();

      res.json(tag);
    } catch (err) {
      console.error(err.message);
      res.status(500).send('Server Error');
    }
  }
);

// @route   PUT api/tags/:id
// @desc    Update a tag
// @access  Private/Admin
router.put('/:id', auth, async (req, res) => {
  try {
    // Check if user is admin
    if (req.user.role !== 'admin') {
      return res.status(403).json({ msg: 'Not authorized' });
    }

    const { name, color } = req.body;

    // Build tag object
    const tagFields = {};
    if (name) tagFields.name = name;
    if (color) tagFields.color = color;

    let tag = await Tag.findById(req.params.id);

    if (!tag) {
      return res.status(404).json({ msg: 'Tag not found' });
    }

    // If name is being changed, check if it already exists
    if (name && name !== tag.name) {
      const existingTag = await Tag.findOne({ name });
      
      if (existingTag) {
        return res.status(400).json({ msg: 'Tag name already exists' });
      }
    }

    tag = await Tag.findByIdAndUpdate(
      req.params.id,
      { $set: tagFields },
      { new: true }
    );

    res.json(tag);
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

// @route   DELETE api/tags/:id
// @desc    Delete a tag
// @access  Private/Admin
router.delete('/:id', auth, async (req, res) => {
  try {
    // Check if user is admin
    if (req.user.role !== 'admin') {
      return res.status(403).json({ msg: 'Not authorized' });
    }

    const tag = await Tag.findById(req.params.id);

    if (!tag) {
      return res.status(404).json({ msg: 'Tag not found' });
    }

    await tag.remove();

    res.json({ msg: 'Tag removed' });
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

module.exports = router;