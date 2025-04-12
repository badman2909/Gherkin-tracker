const express = require('express');
const router = express.Router();
const auth = require('../../middleware/auth');

// @route   GET api/validator/test
// @desc    Test validator route
// @access  Public
router.get('/test', (req, res) => {
  res.json({ msg: 'Validator route works' });
});

// @route   POST api/validator/validate
// @desc    Validate Gherkin content
// @access  Private
router.post('/validate', auth, async (req, res) => {
  try {
    const { content } = req.body;
    
    if (!content) {
      return res.status(400).json({ msg: 'Content is required' });
    }
    
    // Simple validation logic - in a real app, you would use a Gherkin parser
    const lines = content.split('\n');
    const featureCount = (content.match(/Feature:/g) || []).length;
    const scenarioCount = (content.match(/Scenario:/g) || []).length + (content.match(/Scenario Outline:/g) || []).length;
    const stepCount = (content.match(/Given |When |Then |And |But /g) || []).length;
    const examplesCount = (content.match(/Examples:/g) || []).length;
    
    const validation = {
      isValid: true,
      errors: [],
      warnings: [],
      stats: {
        featureCount,
        scenarioCount,
        stepCount,
        examplesCount
      }
    };
    
    res.json(validation);
  } catch (err) {
    console.error('Validate error:', err.message);
    res.status(500).json({ msg: 'Server Error', error: err.message });
  }
});

// @route   POST api/validator/download-file
// @desc    Download a feature file from a URL
// @access  Private
router.post('/download-file', auth, async (req, res) => {
  try {
    const { url } = req.body;
    
    if (!url) {
      return res.status(400).json({ msg: 'URL is required' });
    }
    
    // Mock response for now
    const mockFile = {
      name: 'downloaded-feature.feature',
      path: '/features/downloaded-feature.feature',
      content: `Feature: Downloaded Feature
  As a user
  I want to download feature files
  So that I can use them in my project

  Scenario: Download a feature file
    Given I have a URL to a feature file
    When I download the file
    Then I should see the file content
      `
    };
    
    res.json([mockFile]);
  } catch (err) {
    console.error('Download file error:', err.message);
    res.status(500).json({ msg: 'Server Error', error: err.message });
  }
});

// @route   POST api/validator/download-test-plan
// @desc    Download a test plan from Azure DevOps
// @access  Private
router.post('/download-test-plan', auth, async (req, res) => {
  try {
    const { projectId, testPlanId } = req.body;
    
    if (!projectId || !testPlanId) {
      return res.status(400).json({ msg: 'Project ID and Test Plan ID are required' });
    }
    
    // Mock response for now
    const mockFiles = [
      {
        name: 'test-plan-feature-1.feature',
        path: `/features/${projectId}/${testPlanId}/test-plan-feature-1.feature`,
        content: `Feature: Test Plan Feature 1
  As a tester
  I want to execute test cases from a test plan
  So that I can verify the functionality

  Scenario: Execute test case 1
    Given I have a test plan
    When I execute test case 1
    Then I should see the results
        `
      },
      {
        name: 'test-plan-feature-2.feature',
        path: `/features/${projectId}/${testPlanId}/test-plan-feature-2.feature`,
        content: `Feature: Test Plan Feature 2
  As a tester
  I want to execute test cases from a test plan
  So that I can verify the functionality

  Scenario: Execute test case 2
    Given I have a test plan
    When I execute test case 2
    Then I should see the results
        `
      }
    ];
    
    res.json(mockFiles);
  } catch (err) {
    console.error('Download test plan error:', err.message);
    res.status(500).json({ msg: 'Server Error', error: err.message });
  }
});

module.exports = router;