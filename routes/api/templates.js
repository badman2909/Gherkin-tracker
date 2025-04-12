const express = require('express');
const router = express.Router();
const auth = require('../../middleware/auth');
const { check, validationResult } = require('express-validator');

const Template = require('../../models/Template');
const User = require('../../models/User');

// @route   GET api/templates
// @desc    Get all templates
// @access  Private
router.get('/', auth, async (req, res) => {
  try {
    // Get user's templates and public templates
    const templates = await Template.find({
      $or: [
        { user: req.user.id },
        { isPublic: true }
      ]
    }).sort({ date: -1 });
    
    res.json(templates);
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

// @route   GET api/templates/:id
// @desc    Get template by ID
// @access  Private
router.get('/:id', auth, async (req, res) => {
  try {
    const template = await Template.findById(req.params.id);
    
    if (!template) {
      return res.status(404).json({ msg: 'Template not found' });
    }
    
    // Check if template belongs to user or is public
    if (template.user.toString() !== req.user.id && !template.isPublic) {
      return res.status(401).json({ msg: 'Not authorized to view this template' });
    }
    
    res.json(template);
  } catch (err) {
    console.error(err.message);
    
    if (err.kind === 'ObjectId') {
      return res.status(404).json({ msg: 'Template not found' });
    }
    
    res.status(500).send('Server Error');
  }
});

// @route   POST api/templates
// @desc    Create a template
// @access  Private
router.post(
  '/',
  [
    auth,
    [
      check('name', 'Name is required').not().isEmpty(),
      check('content', 'Content is required').not().isEmpty()
    ]
  ],
  async (req, res) => {
    const errors = validationResult(req);
    if (!errors.isEmpty()) {
      return res.status(400).json({ errors: errors.array() });
    }
    
    try {
      const { name, description, content, tags, isPublic } = req.body;
      
      const newTemplate = new Template({
        name,
        description,
        content,
        tags,
        isPublic: isPublic || false,
        user: req.user.id
      });
      
      const template = await newTemplate.save();
      
      res.json(template);
    } catch (err) {
      console.error(err.message);
      res.status(500).send('Server Error');
    }
  }
);

// @route   PUT api/templates/:id
// @desc    Update a template
// @access  Private
router.put('/:id', auth, async (req, res) => {
  try {
    const template = await Template.findById(req.params.id);
    
    if (!template) {
      return res.status(404).json({ msg: 'Template not found' });
    }
    
    // Check if template belongs to user
    if (template.user.toString() !== req.user.id) {
      return res.status(401).json({ msg: 'Not authorized to update this template' });
    }
    
    const { name, description, content, tags, isPublic } = req.body;
    
    // Update fields
    if (name) template.name = name;
    if (description !== undefined) template.description = description;
    if (content) template.content = content;
    if (tags) template.tags = tags;
    if (isPublic !== undefined) template.isPublic = isPublic;
    
    await template.save();
    
    res.json(template);
  } catch (err) {
    console.error(err.message);
    
    if (err.kind === 'ObjectId') {
      return res.status(404).json({ msg: 'Template not found' });
    }
    
    res.status(500).send('Server Error');
  }
});

// @route   DELETE api/templates/:id
// @desc    Delete a template
// @access  Private
router.delete('/:id', auth, async (req, res) => {
  try {
    const template = await Template.findById(req.params.id);
    
    if (!template) {
      return res.status(404).json({ msg: 'Template not found' });
    }
    
    // Check if template belongs to user
    if (template.user.toString() !== req.user.id) {
      return res.status(401).json({ msg: 'Not authorized to delete this template' });
    }
    
    await template.remove();
    
    res.json({ msg: 'Template removed' });
  } catch (err) {
    console.error(err.message);
    
    if (err.kind === 'ObjectId') {
      return res.status(404).json({ msg: 'Template not found' });
    }
    
    res.status(500).send('Server Error');
  }
});

module.exports = router;