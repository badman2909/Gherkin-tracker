const express = require('express');
const router = express.Router();
const auth = require('../../middleware/auth');
const { check, validationResult } = require('express-validator');
const fs = require('fs');
const path = require('path');

const Keyword = require('../../models/Keyword');
const Domain = require('../../models/Domain');
const Template = require('../../models/Template');

// @route   GET api/reports/keywords
// @desc    Generate a report of keywords
// @access  Private
router.get('/keywords', auth, async (req, res) => {
  try {
    const { format, domain, timeRange } = req.query;
    
    // Build query
    const query = { user: req.user.id };
    
    // Add domain filter if provided
    if (domain) {
      query.domain = domain;
    }
    
    // Add time range filter if provided
    if (timeRange) {
      const now = new Date();
      let cutoffDate;
      
      switch (timeRange) {
        case 'week':
          cutoffDate = new Date(now.setDate(now.getDate() - 7));
          break;
        case 'month':
          cutoffDate = new Date(now.setMonth(now.getMonth() - 1));
          break;
        case 'quarter':
          cutoffDate = new Date(now.setMonth(now.getMonth() - 3));
          break;
        case 'year':
          cutoffDate = new Date(now.setFullYear(now.getFullYear() - 1));
          break;
        default:
          // No time filter
          break;
      }
      
      if (cutoffDate) {
        query.date = { $gte: cutoffDate };
      }
    }
    
    // Get keywords
    const keywords = await Keyword.find(query).sort({ date: -1 });
    
    // Format the report based on requested format
    switch (format) {
      case 'csv':
        // Generate CSV
        const csvHeader = 'Type,Text,Domain,Date\n';
        const csvRows = keywords.map(keyword => {
          const date = new Date(keyword.date).toISOString().split('T')[0];
          return `${keyword.type},"${keyword.text.replace(/"/g, '""')}",${keyword.domain || ''},${date}`;
        });
        const csvContent = csvHeader + csvRows.join('\n');
        
        // Set headers for file download
        res.setHeader('Content-Type', 'text/csv');
        res.setHeader('Content-Disposition', 'attachment; filename=keywords-report.csv');
        
        return res.send(csvContent);
        
      case 'json':
        // Return JSON directly
        return res.json(keywords);
        
      default:
        // Default to JSON if format not specified
        return res.json(keywords);
    }
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

// @route   GET api/reports/domains
// @desc    Generate a report of domains
// @access  Private
router.get('/domains', auth, async (req, res) => {
  try {
    const { format } = req.query;
    
    // Get domains
    const domains = await Domain.find({ user: req.user.id }).sort({ name: 1 });
    
    // For each domain, count the number of keywords
    const domainsWithCounts = await Promise.all(
      domains.map(async (domain) => {
        const keywordCount = await Keyword.countDocuments({ 
          user: req.user.id,
          domain: domain.name 
        });
        
        return {
          _id: domain._id,
          name: domain.name,
          description: domain.description,
          keywordCount
        };
      })
    );
    
    // Format the report based on requested format
    switch (format) {
      case 'csv':
        // Generate CSV
        const csvHeader = 'Name,Description,Keyword Count\n';
        const csvRows = domainsWithCounts.map(domain => {
          return `"${domain.name.replace(/"/g, '""')}","${(domain.description || '').replace(/"/g, '""')}",${domain.keywordCount}`;
        });
        const csvContent = csvHeader + csvRows.join('\n');
        
        // Set headers for file download
        res.setHeader('Content-Type', 'text/csv');
        res.setHeader('Content-Disposition', 'attachment; filename=domains-report.csv');
        
        return res.send(csvContent);
        
      case 'json':
        // Return JSON directly
        return res.json(domainsWithCounts);
        
      default:
        // Default to JSON if format not specified
        return res.json(domainsWithCounts);
    }
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

// @route   GET api/reports/summary
// @desc    Generate a summary report
// @access  Private
router.get('/summary', auth, async (req, res) => {
  try {
    // Count total keywords
    const keywordCount = await Keyword.countDocuments({ user: req.user.id });
    
    // Count keywords by type
    const keywordsByType = await Keyword.aggregate([
      { $match: { user: req.user.id } },
      { $group: { _id: '$type', count: { $sum: 1 } } },
      { $sort: { count: -1 } }
    ]);
    
    // Count domains
    const domainCount = await Domain.countDocuments({ user: req.user.id });
    
    // Count templates
    const templateCount = await Template.countDocuments({ user: req.user.id });
    
    // Get recent keywords
    const recentKeywords = await Keyword.find({ user: req.user.id })
      .sort({ date: -1 })
      .limit(5);
    
    // Prepare summary data
    const summary = {
      keywordCount,
      keywordsByType,
      domainCount,
      templateCount,
      recentKeywords
    };
    
    res.json(summary);
  } catch (err) {
    console.error(err.message);
    res.status(500).send('Server Error');
  }
});

module.exports = router;