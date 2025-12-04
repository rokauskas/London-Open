#!/usr/bin/env node

/**
 * Analyze Monday Trading Patterns in DAX Data
 * 
 * This script analyzes all Mondays in the database to identify statistical edges
 * and trading opportunities based on:
 * - Opening gaps (Sunday close vs Monday open)
 * - First hour price action
 * - High/Low ranges
 * - Closing behavior
 * - Volume patterns
 * - Time-of-day analysis
 * 
 * Usage:
 *   node bin/analyze_monday_patterns.js
 *   node bin/analyze_monday_patterns.js --interval 5m
 *   node bin/analyze_monday_patterns.js --interval 1m
 */

const { MongoClient } = require('mongodb');
const fs = require('fs');
const path = require('path');

// Load MongoDB configuration
const CONFIG_PATH = path.join(__dirname, '..', 'etc', 'mongodb_config.json');
if (!fs.existsSync(CONFIG_PATH)) {
  console.error('ERROR: MongoDB config file not found at:', CONFIG_PATH);
  process.exit(1);
}
const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
const MONGODB_URI = config.connection_string;
const DATABASE_NAME = config.database || 'dax_trading';

// Parse command line arguments
const args = process.argv.slice(2);
let INTERVAL = '5m';
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--interval' && args[i + 1]) {
    INTERVAL = args[i + 1];
  }
}
const COLLECTION_NAME = INTERVAL === '1m' ? 'ohlc_1min' : 'ohlc_5min';

// Helper functions
function calculateStats(values) {
  if (values.length === 0) return { mean: 0, median: 0, stdDev: 0, min: 0, max: 0 };
  
  const sorted = [...values].sort((a, b) => a - b);
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  const median = sorted[Math.floor(sorted.length / 2)];
  const variance = values.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / values.length;
  const stdDev = Math.sqrt(variance);
  
  return {
    mean,
    median,
    stdDev,
    min: sorted[0],
    max: sorted[sorted.length - 1],
    q25: sorted[Math.floor(sorted.length * 0.25)],
    q75: sorted[Math.floor(sorted.length * 0.75)]
  };
}

function formatNumber(num, decimals = 2) {
  return num.toFixed(decimals);
}

function printSection(title) {
  console.log('\n' + '='.repeat(80));
  console.log(title);
  console.log('='.repeat(80));
}

/**
 * Analyze Monday patterns
 */
async function analyzeMondayPatterns() {
  const client = new MongoClient(MONGODB_URI, {
    serverSelectionTimeoutMS: 30000,
    socketTimeoutMS: 60000,
  });

  try {
    await client.connect();
    console.log(`Connected to MongoDB: ${DATABASE_NAME}.${COLLECTION_NAME}`);
    
    const db = client.db(DATABASE_NAME);
    const collection = db.collection(COLLECTION_NAME);

    // Get all unique Monday dates
    printSection('FETCHING MONDAY DATA');
    const mondayDates = await collection.distinct('session_date', { 
      day_of_week: 'Monday' 
    });
    console.log(`Found ${mondayDates.length} Mondays in database`);

    if (mondayDates.length === 0) {
      console.log('\nNo Monday data found. Please add day_of_week field using analyze_data_gaps.js');
      return;
    }

    // Analyze each Monday
    const mondayStats = [];
    
    for (const date of mondayDates) {
      const candles = await collection.find({ 
        session_date: date 
      }).sort({ timestamp: 1 }).toArray();

      if (candles.length === 0) continue;

      const firstCandle = candles[0];
      const lastCandle = candles[candles.length - 1];
      
      // Get first hour candles (12 x 5min or 60 x 1min)
      const candlesPerHour = INTERVAL === '1m' ? 60 : 12;
      const firstHourCandles = candles.slice(0, Math.min(candlesPerHour, candles.length));
      
      // Calculate daily metrics
      const dailyHigh = Math.max(...candles.map(c => c.high));
      const dailyLow = Math.min(...candles.map(c => c.low));
      const dailyRange = dailyHigh - dailyLow;
      const dailyChange = lastCandle.close - firstCandle.open;
      const dailyChangePercent = (dailyChange / firstCandle.open) * 100;
      
      // First hour metrics
      const firstHourHigh = Math.max(...firstHourCandles.map(c => c.high));
      const firstHourLow = Math.min(...firstHourCandles.map(c => c.low));
      const firstHourRange = firstHourHigh - firstHourLow;
      const firstHourClose = firstHourCandles[firstHourCandles.length - 1].close;
      const firstHourChange = firstHourClose - firstCandle.open;
      const firstHourChangePercent = (firstHourChange / firstCandle.open) * 100;
      
      // Opening characteristics
      const openPrice = firstCandle.open;
      const highLowMidpoint = (dailyHigh + dailyLow) / 2;
      const openRelativeToRange = ((openPrice - dailyLow) / dailyRange) * 100; // Where did it open in daily range?
      
      // Closing characteristics
      const closeRelativeToRange = ((lastCandle.close - dailyLow) / dailyRange) * 100;
      const closedInUpperHalf = closeRelativeToRange > 50;
      const closedInLowerHalf = closeRelativeToRange < 50;
      
      // Direction bias
      const bullishDay = dailyChange > 0;
      const bearishDay = dailyChange < 0;
      const firstHourBullish = firstHourChange > 0;
      const firstHourBearish = firstHourChange < 0;
      
      // Volume analysis
      const totalVolume = candles.reduce((sum, c) => sum + (c.volume || 0), 0);
      const avgVolume = totalVolume / candles.length;
      const firstHourVolume = firstHourCandles.reduce((sum, c) => sum + (c.volume || 0), 0);
      const firstHourVolumePercent = (firstHourVolume / totalVolume) * 100;
      
      mondayStats.push({
        date,
        open: openPrice,
        close: lastCandle.close,
        high: dailyHigh,
        low: dailyLow,
        dailyRange,
        dailyChange,
        dailyChangePercent,
        firstHourRange,
        firstHourChange,
        firstHourChangePercent,
        openRelativeToRange,
        closeRelativeToRange,
        closedInUpperHalf,
        closedInLowerHalf,
        bullishDay,
        bearishDay,
        firstHourBullish,
        firstHourBearish,
        totalVolume,
        avgVolume,
        firstHourVolume,
        firstHourVolumePercent,
        candleCount: candles.length
      });
    }

    // QUANTITATIVE ANALYSIS
    printSection('1. OVERALL MONDAY STATISTICS');
    
    const bullishDays = mondayStats.filter(s => s.bullishDay).length;
    const bearishDays = mondayStats.filter(s => s.bearishDay).length;
    const bullishPercent = (bullishDays / mondayStats.length) * 100;
    
    console.log(`Total Mondays analyzed: ${mondayStats.length}`);
    console.log(`Bullish Mondays: ${bullishDays} (${formatNumber(bullishPercent)}%)`);
    console.log(`Bearish Mondays: ${bearishDays} (${formatNumber(100 - bullishPercent)}%)`);
    console.log(`\n** EDGE: Mondays are ${bullishPercent > 50 ? 'BULLISH' : 'BEARISH'} biased by ${formatNumber(Math.abs(bullishPercent - 50))}% **`);

    // Daily range statistics
    printSection('2. DAILY RANGE ANALYSIS');
    const rangeStats = calculateStats(mondayStats.map(s => s.dailyRange));
    console.log(`Average daily range: ${formatNumber(rangeStats.mean)} points`);
    console.log(`Median daily range: ${formatNumber(rangeStats.median)} points`);
    console.log(`Range StdDev: ${formatNumber(rangeStats.stdDev)} points`);
    console.log(`Min range: ${formatNumber(rangeStats.min)} points`);
    console.log(`Max range: ${formatNumber(rangeStats.max)} points`);
    console.log(`25th percentile: ${formatNumber(rangeStats.q25)} points`);
    console.log(`75th percentile: ${formatNumber(rangeStats.q75)} points`);
    console.log(`\n** EDGE: Expect Monday range of ${formatNumber(rangeStats.q25)}-${formatNumber(rangeStats.q75)} points (50% of days) **`);

    // First hour analysis
    printSection('3. FIRST HOUR ANALYSIS');
    const firstHourBullish = mondayStats.filter(s => s.firstHourBullish).length;
    const firstHourBullishPercent = (firstHourBullish / mondayStats.length) * 100;
    const firstHourRangeStats = calculateStats(mondayStats.map(s => s.firstHourRange));
    const firstHourChangeStats = calculateStats(mondayStats.map(s => s.firstHourChangePercent));
    
    console.log(`First hour bullish: ${firstHourBullish} (${formatNumber(firstHourBullishPercent)}%)`);
    console.log(`First hour bearish: ${mondayStats.length - firstHourBullish} (${formatNumber(100 - firstHourBullishPercent)}%)`);
    console.log(`\nFirst hour average range: ${formatNumber(firstHourRangeStats.mean)} points`);
    console.log(`First hour median range: ${formatNumber(firstHourRangeStats.median)} points`);
    console.log(`First hour average change: ${formatNumber(firstHourChangeStats.mean)}%`);
    console.log(`First hour StdDev: ${formatNumber(firstHourChangeStats.stdDev)}%`);
    
    // Calculate percentage of daily range achieved in first hour
    const firstHourRangePercents = mondayStats.map(s => (s.firstHourRange / s.dailyRange) * 100);
    const firstHourRangePercentStats = calculateStats(firstHourRangePercents);
    console.log(`\nFirst hour captures ${formatNumber(firstHourRangePercentStats.mean)}% of daily range on average`);
    console.log(`\n** EDGE: First hour ${firstHourBullishPercent > 50 ? 'tends BULLISH' : 'tends BEARISH'} (${formatNumber(Math.abs(firstHourBullishPercent - 50))}% edge) **`);
    console.log(`** EDGE: First hour typically moves ${formatNumber(firstHourRangeStats.median)} points **`);

    // Opening position analysis
    printSection('4. OPENING POSITION IN DAILY RANGE');
    const openStats = calculateStats(mondayStats.map(s => s.openRelativeToRange));
    console.log(`Average opening position: ${formatNumber(openStats.mean)}% of daily range`);
    console.log(`Median opening position: ${formatNumber(openStats.median)}% of daily range`);
    console.log(`StdDev: ${formatNumber(openStats.stdDev)}%`);
    
    const opensLower = mondayStats.filter(s => s.openRelativeToRange < 40).length;
    const opensMiddle = mondayStats.filter(s => s.openRelativeToRange >= 40 && s.openRelativeToRange <= 60).length;
    const opensUpper = mondayStats.filter(s => s.openRelativeToRange > 60).length;
    
    console.log(`\nOpens in lower 40%: ${opensLower} (${formatNumber((opensLower / mondayStats.length) * 100)}%)`);
    console.log(`Opens in middle 20%: ${opensMiddle} (${formatNumber((opensMiddle / mondayStats.length) * 100)}%)`);
    console.log(`Opens in upper 40%: ${opensUpper} (${formatNumber((opensUpper / mondayStats.length) * 100)}%)`);
    console.log(`\n** EDGE: Mondays typically open at ${formatNumber(openStats.median)}% of daily range **`);

    // Closing position analysis
    printSection('5. CLOSING POSITION ANALYSIS');
    const closeStats = calculateStats(mondayStats.map(s => s.closeRelativeToRange));
    const closedUpper = mondayStats.filter(s => s.closedInUpperHalf).length;
    const closedLower = mondayStats.filter(s => s.closedInLowerHalf).length;
    
    console.log(`Average closing position: ${formatNumber(closeStats.mean)}% of daily range`);
    console.log(`Closed in upper half: ${closedUpper} (${formatNumber((closedUpper / mondayStats.length) * 100)}%)`);
    console.log(`Closed in lower half: ${closedLower} (${formatNumber((closedLower / mondayStats.length) * 100)}%)`);
    console.log(`\n** EDGE: Mondays ${closedUpper > closedLower ? 'prefer closing HIGHER' : 'prefer closing LOWER'} (${formatNumber(Math.abs((closedUpper - closedLower) / mondayStats.length * 100))}% edge) **`);

    // Correlation: First hour predicts day?
    printSection('6. PREDICTIVE ANALYSIS: Does First Hour Predict Day?');
    const firstHourBullishDayBullish = mondayStats.filter(s => s.firstHourBullish && s.bullishDay).length;
    const firstHourBearishDayBearish = mondayStats.filter(s => s.firstHourBearish && s.bearishDay).length;
    const firstHourCorrect = firstHourBullishDayBullish + firstHourBearishDayBearish;
    const predictionAccuracy = (firstHourCorrect / mondayStats.length) * 100;
    
    console.log(`First hour bullish → Day bullish: ${firstHourBullishDayBullish}/${firstHourBullish} (${formatNumber((firstHourBullishDayBullish / firstHourBullish) * 100)}%)`);
    console.log(`First hour bearish → Day bearish: ${firstHourBearishDayBearish}/${mondayStats.length - firstHourBullish} (${formatNumber((firstHourBearishDayBearish / (mondayStats.length - firstHourBullish)) * 100)}%)`);
    console.log(`\nOverall prediction accuracy: ${formatNumber(predictionAccuracy)}%`);
    console.log(`\n** EDGE: First hour direction predicts daily direction ${formatNumber(predictionAccuracy)}% of the time **`);
    if (predictionAccuracy > 60) {
      console.log(`** STRONG EDGE: This is a significant predictive edge! **`);
    } else if (predictionAccuracy < 40) {
      console.log(`** CONTRARIAN EDGE: Consider fading first hour direction! **`);
    }

    // Volume analysis
    printSection('7. VOLUME ANALYSIS');
    const volumeStats = calculateStats(mondayStats.map(s => s.avgVolume));
    const firstHourVolPercStats = calculateStats(mondayStats.map(s => s.firstHourVolumePercent));
    
    console.log(`Average volume per candle: ${formatNumber(volumeStats.mean, 0)}`);
    console.log(`Median volume per candle: ${formatNumber(volumeStats.median, 0)}`);
    console.log(`\nFirst hour volume as % of daily: ${formatNumber(firstHourVolPercStats.mean)}%`);
    console.log(`First hour volume median: ${formatNumber(firstHourVolPercStats.median)}%`);
    console.log(`\n** EDGE: First hour concentrates ${formatNumber(firstHourVolPercStats.median)}% of daily volume **`);

    // Trading recommendations
    printSection('8. TRADING EDGES & RECOMMENDATIONS');
    console.log('\n📊 QUANTITATIVE EDGES DISCOVERED:');
    console.log('');
    
    if (bullishPercent > 55) {
      console.log(`✓ DIRECTIONAL EDGE: ${formatNumber(bullishPercent)}% bullish bias on Mondays`);
      console.log(`  → Strategy: Favor long positions, buy dips`);
    } else if (bullishPercent < 45) {
      console.log(`✓ DIRECTIONAL EDGE: ${formatNumber(100 - bullishPercent)}% bearish bias on Mondays`);
      console.log(`  → Strategy: Favor short positions, sell rallies`);
    }
    
    console.log(`\n✓ RANGE EDGE: Expected range ${formatNumber(rangeStats.q25)}-${formatNumber(rangeStats.q75)} points`);
    console.log(`  → Strategy: Set profit targets at ${formatNumber(rangeStats.median)} points from entry`);
    
    console.log(`\n✓ FIRST HOUR EDGE: Captures ${formatNumber(firstHourRangePercentStats.mean)}% of daily range`);
    console.log(`  → Strategy: Focus on first hour for entries, expect ${formatNumber(firstHourRangeStats.median)} point moves`);
    
    if (predictionAccuracy > 60) {
      console.log(`\n✓ PREDICTIVE EDGE: First hour predicts day ${formatNumber(predictionAccuracy)}% accuracy`);
      console.log(`  → Strategy: Follow first hour direction for day trades`);
    } else if (predictionAccuracy < 40) {
      console.log(`\n✓ CONTRARIAN EDGE: First hour fails ${formatNumber(100 - predictionAccuracy)}% of time`);
      console.log(`  → Strategy: Fade first hour extremes, look for reversals`);
    }
    
    if (closedUpper > closedLower * 1.2) {
      console.log(`\n✓ CLOSING EDGE: ${formatNumber((closedUpper / mondayStats.length) * 100)}% close in upper half`);
      console.log(`  → Strategy: Hold longs into close, close shorts early`);
    } else if (closedLower > closedUpper * 1.2) {
      console.log(`\n✓ CLOSING EDGE: ${formatNumber((closedLower / mondayStats.length) * 100)}% close in lower half`);
      console.log(`  → Strategy: Hold shorts into close, close longs early`);
    }

    // Export detailed data
    printSection('9. EXPORTING DETAILED DATA');
    const outputDir = path.join(__dirname, '..', 'var', 'output');
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }
    
    const csvFile = path.join(outputDir, `monday_analysis_${INTERVAL}_${new Date().toISOString().split('T')[0]}.csv`);
    const csvHeader = 'date,open,close,high,low,daily_range,daily_change_pct,first_hour_range,first_hour_change_pct,open_relative_to_range,close_relative_to_range,bullish_day,first_hour_bullish\n';
    const csvRows = mondayStats.map(s => 
      `${s.date},${s.open},${s.close},${s.high},${s.low},${formatNumber(s.dailyRange)},${formatNumber(s.dailyChangePercent)},${formatNumber(s.firstHourRange)},${formatNumber(s.firstHourChangePercent)},${formatNumber(s.openRelativeToRange)},${formatNumber(s.closeRelativeToRange)},${s.bullishDay ? 1 : 0},${s.firstHourBullish ? 1 : 0}`
    ).join('\n');
    
    fs.writeFileSync(csvFile, csvHeader + csvRows);
    console.log(`\n✓ Detailed data exported to: ${csvFile}`);
    console.log(`  Use this data for further backtesting and analysis`);

    console.log('\n' + '='.repeat(80));
    console.log('ANALYSIS COMPLETE');
    console.log('='.repeat(80));

  } catch (error) {
    console.error('Error:', error.message);
    console.error(error.stack);
  } finally {
    await client.close();
  }
}

// Run analysis
console.log('='.repeat(80));
console.log('MONDAY TRADING PATTERN ANALYSIS');
console.log(`Interval: ${INTERVAL}`);
console.log('='.repeat(80));

analyzeMondayPatterns();
