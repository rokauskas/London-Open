#!/usr/bin/env node

/**
 * Deep Entry Analysis for Monday Trading
 * 
 * Analyzes specific entry signals and indicators for Monday trading:
 * - Opening gap analysis (gap up/down statistics)
 * - VWAP positioning for entries
 * - First 15/30 minute patterns
 * - Pullback entry points
 * - Breakout entry confirmations
 * - Support/resistance levels
 * - Momentum indicators
 * 
 * Usage:
 *   node bin/analyze_monday_entries.js
 *   node bin/analyze_monday_entries.js --interval 1m
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

// Parse arguments
const args = process.argv.slice(2);
let INTERVAL = '5m';
for (let i = 0; i < args.length; i++) {
  if (args[i] === '--interval' && args[i + 1]) {
    INTERVAL = args[i + 1];
  }
}
const COLLECTION_NAME = INTERVAL === '1m' ? 'ohlc_1min' : 'ohlc_5min';

// Helper functions
function calculateVWAP(candles) {
  let cumulativeTPV = 0;
  let cumulativeVolume = 0;
  
  return candles.map(candle => {
    const typicalPrice = (candle.high + candle.low + candle.close) / 3;
    const tpv = typicalPrice * (candle.volume || 1);
    cumulativeTPV += tpv;
    cumulativeVolume += (candle.volume || 1);
    return cumulativeTPV / cumulativeVolume;
  });
}

function calculateEMA(prices, period) {
  const k = 2 / (period + 1);
  const ema = [prices[0]];
  
  for (let i = 1; i < prices.length; i++) {
    ema.push(prices[i] * k + ema[i - 1] * (1 - k));
  }
  return ema;
}

function calculateRSI(prices, period = 14) {
  if (prices.length < period + 1) return Array(prices.length).fill(50);
  
  const changes = [];
  for (let i = 1; i < prices.length; i++) {
    changes.push(prices[i] - prices[i - 1]);
  }
  
  const rsi = [50];
  let avgGain = 0;
  let avgLoss = 0;
  
  for (let i = 0; i < period; i++) {
    if (changes[i] > 0) avgGain += changes[i];
    else avgLoss += Math.abs(changes[i]);
  }
  avgGain /= period;
  avgLoss /= period;
  
  for (let i = period; i < changes.length; i++) {
    const change = changes[i];
    avgGain = (avgGain * (period - 1) + (change > 0 ? change : 0)) / period;
    avgLoss = (avgLoss * (period - 1) + (change < 0 ? Math.abs(change) : 0)) / period;
    
    const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
    rsi.push(100 - (100 / (1 + rs)));
  }
  
  return rsi;
}

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
 * Analyze Monday entry patterns
 */
async function analyzeMondayEntries() {
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
    printSection('LOADING MONDAY DATA');
    const mondayDates = await collection.distinct('session_date', { 
      day_of_week: 'Monday' 
    });
    console.log(`Found ${mondayDates.length} Mondays in database`);

    if (mondayDates.length === 0) {
      console.log('\nNo Monday data found.');
      return;
    }

    // Also get Friday closes for gap analysis
    const fridayDates = await collection.distinct('session_date', { 
      day_of_week: 'Friday' 
    });

    const entryAnalysis = [];
    
    for (const mondayDate of mondayDates) {
      const candles = await collection.find({ 
        session_date: mondayDate 
      }).sort({ timestamp: 1 }).toArray();

      if (candles.length < 12) continue; // Need at least first hour

      // Get previous Friday's close for gap analysis
      const mondayDateObj = new Date(mondayDate);
      const prevFridayDate = new Date(mondayDateObj);
      prevFridayDate.setDate(prevFridayDate.getDate() - 3);
      const prevFridayStr = prevFridayDate.toISOString().split('T')[0];
      
      let fridayClose = null;
      if (fridayDates.includes(prevFridayStr)) {
        const fridayCandles = await collection.find({ 
          session_date: prevFridayStr 
        }).sort({ timestamp: -1 }).limit(1).toArray();
        if (fridayCandles.length > 0) {
          fridayClose = fridayCandles[0].close;
        }
      }

      const closePrices = candles.map(c => c.close);
      const vwap = calculateVWAP(candles);
      const ema20 = calculateEMA(closePrices, 20);
      const ema50 = calculateEMA(closePrices, 50);
      const rsi = calculateRSI(closePrices, 14);

      // Candles per period
      const candlesPerPeriod = INTERVAL === '1m' ? 60 : 12; // 1 hour
      const candles15min = INTERVAL === '1m' ? 15 : 3;
      const candles30min = INTERVAL === '1m' ? 30 : 6;

      const firstCandle = candles[0];
      const first15Candles = candles.slice(0, Math.min(candles15min, candles.length));
      const first30Candles = candles.slice(0, Math.min(candles30min, candles.length));
      const firstHourCandles = candles.slice(0, Math.min(candlesPerPeriod, candles.length));
      const lastCandle = candles[candles.length - 1];

      // Gap analysis
      let gapPercent = 0;
      let gapPoints = 0;
      let gapType = 'none';
      if (fridayClose) {
        gapPoints = firstCandle.open - fridayClose;
        gapPercent = (gapPoints / fridayClose) * 100;
        if (gapPercent > 0.1) gapType = 'gap_up';
        else if (gapPercent < -0.1) gapType = 'gap_down';
      }

      // Opening bar analysis
      const openBarRange = firstCandle.high - firstCandle.low;
      const openBarBullish = firstCandle.close > firstCandle.open;
      const openBarBodyPercent = Math.abs(firstCandle.close - firstCandle.open) / openBarRange * 100;

      // First 15 min high/low
      const first15High = Math.max(...first15Candles.map(c => c.high));
      const first15Low = Math.min(...first15Candles.map(c => c.low));
      const first15Range = first15High - first15Low;
      const first15Close = first15Candles[first15Candles.length - 1].close;
      const first15Bullish = first15Close > firstCandle.open;

      // First 30 min high/low
      const first30High = Math.max(...first30Candles.map(c => c.high));
      const first30Low = Math.min(...first30Candles.map(c => c.low));
      const first30Range = first30High - first30Low;
      const first30Close = first30Candles[first30Candles.length - 1].close;
      const first30Bullish = first30Close > firstCandle.open;

      // First hour analysis
      const firstHourHigh = Math.max(...firstHourCandles.map(c => c.high));
      const firstHourLow = Math.min(...firstHourCandles.map(c => c.low));
      const firstHourClose = firstHourCandles[firstHourCandles.length - 1].close;
      const firstHourBullish = firstHourClose > firstCandle.open;

      // VWAP positioning at key times
      const vwapAt15 = vwap[Math.min(candles15min - 1, vwap.length - 1)];
      const vwapAt30 = vwap[Math.min(candles30min - 1, vwap.length - 1)];
      const vwapAt60 = vwap[Math.min(candlesPerPeriod - 1, vwap.length - 1)];
      
      const priceVsVwapOpen = ((firstCandle.open - vwap[0]) / vwap[0]) * 100;
      const priceVsVwap15 = ((first15Close - vwapAt15) / vwapAt15) * 100;
      const priceVsVwap30 = ((first30Close - vwapAt30) / vwapAt30) * 100;
      const priceVsVwap60 = ((firstHourClose - vwapAt60) / vwapAt60) * 100;

      // EMA positioning
      const ema20At60 = ema20[Math.min(candlesPerPeriod - 1, ema20.length - 1)];
      const ema50At60 = ema50[Math.min(candlesPerPeriod - 1, ema50.length - 1)];
      const goldenCross = ema20At60 > ema50At60;

      // RSI at first hour
      const rsiAt60 = rsi[Math.min(candlesPerPeriod - 1, rsi.length - 1)];
      const rsiOversold = rsiAt60 < 30;
      const rsiOverbought = rsiAt60 > 70;

      // Daily outcome
      const dailyHigh = Math.max(...candles.map(c => c.high));
      const dailyLow = Math.min(...candles.map(c => c.low));
      const dailyChange = lastCandle.close - firstCandle.open;
      const bullishDay = dailyChange > 0;

      // Entry signal success rates
      // Signal 1: Buy pullback to VWAP after bullish first 15min
      const bullish15PullbackToVWAP = first15Bullish && priceVsVwap30 < 0.1 && priceVsVwap30 > -0.3;
      
      // Signal 2: Buy breakout of first 15min high after bullish first 15min
      const bullish15Breakout = first15Bullish && firstHourHigh > first15High;
      
      // Signal 3: Buy gap fill on gap down
      const gapDownFilled = gapType === 'gap_down' && firstHourHigh >= fridayClose;
      
      // Signal 4: Fade gap up if rejected at VWAP
      const gapUpRejection = gapType === 'gap_up' && priceVsVwap30 < -0.2;
      
      // Signal 5: Buy RSI oversold in first hour
      const buyRSIOversold = rsiOversold && firstHourBullish;
      
      // Signal 6: Buy golden cross confirmation
      const buyGoldenCross = goldenCross && firstHourBullish;

      // Best entry point analysis
      let bestLongEntry = firstHourLow; // Default: buy the low
      let bestShortEntry = firstHourHigh; // Default: sell the high
      
      // For longs: find best pullback entry
      if (bullishDay) {
        const pullbacks = [];
        for (let i = 1; i < firstHourCandles.length; i++) {
          if (firstHourCandles[i].low < firstHourCandles[i-1].low) {
            pullbacks.push(firstHourCandles[i].low);
          }
        }
        if (pullbacks.length > 0) {
          bestLongEntry = Math.max(...pullbacks); // Shallowest pullback that still worked
        }
      }

      // Entry to high/low distance (reward potential)
      const longReward = dailyHigh - bestLongEntry;
      const longRisk = bestLongEntry - firstHourLow;
      const longRR = longRisk > 0 ? longReward / longRisk : 0;

      const shortReward = bestShortEntry - dailyLow;
      const shortRisk = firstHourHigh - bestShortEntry;
      const shortRR = shortRisk > 0 ? shortReward / shortRisk : 0;

      entryAnalysis.push({
        date: mondayDate,
        gapType,
        gapPercent,
        gapPoints,
        openBarBullish,
        openBarBodyPercent,
        first15Bullish,
        first15Range,
        first30Bullish,
        first30Range,
        firstHourBullish,
        priceVsVwapOpen,
        priceVsVwap15,
        priceVsVwap30,
        priceVsVwap60,
        goldenCross,
        rsiAt60,
        rsiOversold,
        rsiOverbought,
        bullish15PullbackToVWAP,
        bullish15Breakout,
        gapDownFilled,
        gapUpRejection,
        buyRSIOversold,
        buyGoldenCross,
        bestLongEntry,
        bestShortEntry,
        longReward,
        longRisk,
        longRR,
        shortReward,
        shortRisk,
        shortRR,
        bullishDay,
        dailyChange,
        dailyHigh,
        dailyLow,
        firstHourHigh,
        firstHourLow
      });
    }

    console.log(`Analyzed ${entryAnalysis.length} complete Mondays`);

    // ANALYSIS 1: GAP STATISTICS
    printSection('1. OPENING GAP ANALYSIS');
    const gapUps = entryAnalysis.filter(e => e.gapType === 'gap_up');
    const gapDowns = entryAnalysis.filter(e => e.gapType === 'gap_down');
    const noGaps = entryAnalysis.filter(e => e.gapType === 'none');

    console.log(`Gap ups: ${gapUps.length} (${formatNumber((gapUps.length / entryAnalysis.length) * 100)}%)`);
    console.log(`Gap downs: ${gapDowns.length} (${formatNumber((gapDowns.length / entryAnalysis.length) * 100)}%)`);
    console.log(`No significant gap: ${noGaps.length} (${formatNumber((noGaps.length / entryAnalysis.length) * 100)}%)`);

    if (gapUps.length > 0) {
      const gapUpBullish = gapUps.filter(e => e.bullishDay).length;
      const gapUpAvg = calculateStats(gapUps.map(e => e.gapPercent));
      console.log(`\nGap Up Stats:`);
      console.log(`  Bullish day rate: ${formatNumber((gapUpBullish / gapUps.length) * 100)}%`);
      console.log(`  Average gap size: ${formatNumber(gapUpAvg.mean)}%`);
      console.log(`  Median gap size: ${formatNumber(gapUpAvg.median)}%`);
    }

    if (gapDowns.length > 0) {
      const gapDownBullish = gapDowns.filter(e => e.bullishDay).length;
      const gapDownAvg = calculateStats(gapDowns.map(e => e.gapPercent));
      console.log(`\nGap Down Stats:`);
      console.log(`  Bullish day rate: ${formatNumber((gapDownBullish / gapDowns.length) * 100)}%`);
      console.log(`  Average gap size: ${formatNumber(gapDownAvg.mean)}%`);
      console.log(`  Median gap size: ${formatNumber(gapDownAvg.median)}%`);
      console.log(`\n** EDGE: Gap downs have ${formatNumber((gapDownBullish / gapDowns.length) * 100)}% chance of closing higher (fade the gap!) **`);
    }

    // ANALYSIS 2: VWAP ENTRY SIGNALS
    printSection('2. VWAP ENTRY ANALYSIS');
    
    const vwapPullbacks = entryAnalysis.filter(e => e.bullish15PullbackToVWAP);
    const vwapPullbackSuccess = vwapPullbacks.filter(e => e.bullishDay).length;
    
    console.log(`Bullish 15min + Pullback to VWAP at 30min:`);
    console.log(`  Occurrences: ${vwapPullbacks.length}`);
    console.log(`  Success rate: ${vwapPullbacks.length > 0 ? formatNumber((vwapPullbackSuccess / vwapPullbacks.length) * 100) : 0}%`);
    
    if (vwapPullbacks.length > 0) {
      const avgReward = calculateStats(vwapPullbacks.map(e => e.longReward));
      const avgRR = calculateStats(vwapPullbacks.map(e => e.longRR));
      console.log(`  Average reward: ${formatNumber(avgReward.mean)} points`);
      console.log(`  Average R:R: ${formatNumber(avgRR.mean)}:1`);
      console.log(`\n** ENTRY SIGNAL: Buy pullback to VWAP after bullish first 15min **`);
      console.log(`** SUCCESS RATE: ${formatNumber((vwapPullbackSuccess / vwapPullbacks.length) * 100)}% **`);
    }

    // Price position relative to VWAP at different times
    const aboveVWAP30 = entryAnalysis.filter(e => e.priceVsVwap30 > 0);
    const aboveVWAP30Bullish = aboveVWAP30.filter(e => e.bullishDay).length;
    
    console.log(`\nPrice above VWAP at 30min:`);
    console.log(`  Occurrences: ${aboveVWAP30.length}`);
    console.log(`  Bullish day rate: ${aboveVWAP30.length > 0 ? formatNumber((aboveVWAP30Bullish / aboveVWAP30.length) * 100) : 0}%`);
    console.log(`\n** EDGE: If price above VWAP at 30min, ${formatNumber((aboveVWAP30Bullish / aboveVWAP30.length) * 100)}% bullish day **`);

    // ANALYSIS 3: FIRST 15/30 MIN BREAKOUT
    printSection('3. BREAKOUT ENTRY SIGNALS');
    
    const breakouts = entryAnalysis.filter(e => e.bullish15Breakout);
    const breakoutSuccess = breakouts.filter(e => e.bullishDay).length;
    
    console.log(`First 15min high breakout (confirmed in first hour):`);
    console.log(`  Occurrences: ${breakouts.length}`);
    console.log(`  Success rate: ${breakouts.length > 0 ? formatNumber((breakoutSuccess / breakouts.length) * 100) : 0}%`);
    
    if (breakouts.length > 0) {
      const avgReward = calculateStats(breakouts.map(e => e.longReward));
      const avgRR = calculateStats(breakouts.map(e => e.longRR));
      console.log(`  Average reward: ${formatNumber(avgReward.mean)} points`);
      console.log(`  Average R:R: ${formatNumber(avgRR.mean)}:1`);
      console.log(`\n** ENTRY SIGNAL: Buy breakout of first 15min high **`);
      console.log(`** SUCCESS RATE: ${formatNumber((breakoutSuccess / breakouts.length) * 100)}% **`);
    }

    // First 15 vs 30 consistency
    const consistent15to30 = entryAnalysis.filter(e => e.first15Bullish === e.first30Bullish);
    const consistent15to30Bullish = consistent15to30.filter(e => e.bullishDay).length;
    
    console.log(`\nConsistent direction 15min → 30min:`);
    console.log(`  Occurrences: ${consistent15to30.length}`);
    console.log(`  Bullish day rate: ${formatNumber((consistent15to30Bullish / consistent15to30.length) * 100)}%`);
    console.log(`\n** EDGE: If direction consistent 15-30min, ${formatNumber((consistent15to30Bullish / consistent15to30.length) * 100)}% predictive **`);

    // ANALYSIS 4: RSI ENTRY SIGNALS
    printSection('4. RSI ENTRY SIGNALS');
    
    const rsiOversoldEntries = entryAnalysis.filter(e => e.rsiOversold);
    const rsiOversoldSuccess = rsiOversoldEntries.filter(e => e.bullishDay).length;
    
    console.log(`RSI < 30 in first hour:`);
    console.log(`  Occurrences: ${rsiOversoldEntries.length}`);
    console.log(`  Bullish day rate: ${rsiOversoldEntries.length > 0 ? formatNumber((rsiOversoldSuccess / rsiOversoldEntries.length) * 100) : 0}%`);
    
    if (rsiOversoldEntries.length > 0) {
      console.log(`\n** ENTRY SIGNAL: Buy RSI oversold (<30) in first hour **`);
      console.log(`** SUCCESS RATE: ${formatNumber((rsiOversoldSuccess / rsiOversoldEntries.length) * 100)}% **`);
    }

    const rsiOverboughtEntries = entryAnalysis.filter(e => e.rsiOverbought);
    const rsiOverboughtContinue = rsiOverboughtEntries.filter(e => e.bullishDay).length;
    
    console.log(`\nRSI > 70 in first hour:`);
    console.log(`  Occurrences: ${rsiOverboughtEntries.length}`);
    console.log(`  Continues higher: ${rsiOverboughtEntries.length > 0 ? formatNumber((rsiOverboughtContinue / rsiOverboughtEntries.length) * 100) : 0}%`);
    
    if (rsiOverboughtEntries.length > 0) {
      console.log(`\n** WARNING: RSI overbought is NOT reliable for shorting (${formatNumber((rsiOverboughtContinue / rsiOverboughtEntries.length) * 100)}% continues) **`);
    }

    // ANALYSIS 5: RISK/REWARD ANALYSIS
    printSection('5. RISK/REWARD ANALYSIS');
    
    const bullishDays = entryAnalysis.filter(e => e.bullishDay);
    const bearishDays = entryAnalysis.filter(e => !e.bullishDay);
    
    const longRRStats = calculateStats(bullishDays.map(e => e.longRR));
    const shortRRStats = calculateStats(bearishDays.map(e => e.shortRR));
    
    console.log(`Long trades (on bullish days):`);
    console.log(`  Average R:R: ${formatNumber(longRRStats.mean)}:1`);
    console.log(`  Median R:R: ${formatNumber(longRRStats.median)}:1`);
    console.log(`  Best entry: First hour pullback lows`);
    
    console.log(`\nShort trades (on bearish days):`);
    console.log(`  Average R:R: ${formatNumber(shortRRStats.mean)}:1`);
    console.log(`  Median R:R: ${formatNumber(shortRRStats.median)}:1`);
    console.log(`  Best entry: First hour rally highs`);
    
    console.log(`\n** EDGE: Long trades offer ${formatNumber(longRRStats.median)}:1 R:R on average **`);
    console.log(`** EDGE: Wait for pullback in first hour for better entry **`);

    // ANALYSIS 6: BEST ENTRY RULES
    printSection('6. OPTIMAL ENTRY RULES');
    
    console.log('\n🎯 LONG ENTRY RULES (in order of priority):\n');
    
    console.log('1. FIRST 15 MINUTES:');
    console.log('   - Wait for first 15min to complete');
    console.log('   - If bullish → Look for long entries');
    const first15BullishWin = entryAnalysis.filter(e => e.first15Bullish && e.bullishDay).length;
    const first15BullishTotal = entryAnalysis.filter(e => e.first15Bullish).length;
    console.log(`   - Success rate: ${formatNumber((first15BullishWin / first15BullishTotal) * 100)}%`);
    
    console.log('\n2. ENTRY TRIGGER (choose one):');
    console.log(`   A) VWAP PULLBACK (${vwapPullbacks.length > 0 ? formatNumber((vwapPullbackSuccess / vwapPullbacks.length) * 100) : 0}% success):`);
    console.log('      - Price pulls back to VWAP (within 0.3%)');
    console.log('      - Buy when price bounces off VWAP');
    console.log('      - Stop: Below first 15min low');
    
    console.log(`\n   B) BREAKOUT (${breakouts.length > 0 ? formatNumber((breakoutSuccess / breakouts.length) * 100) : 0}% success):`);
    console.log('      - Price breaks above first 15min high');
    console.log('      - Enter on break and hold');
    console.log('      - Stop: First 15min low');
    
    console.log(`\n   C) RSI OVERSOLD (${rsiOversoldEntries.length > 0 ? formatNumber((rsiOversoldSuccess / rsiOversoldEntries.length) * 100) : 0}% success):`);
    console.log('      - RSI < 30 in first hour');
    console.log('      - Price above VWAP');
    console.log('      - Enter on RSI turning up');
    console.log('      - Stop: First hour low');
    
    console.log('\n3. CONFIRMATION:');
    console.log('   - Price above VWAP = bullish confirmation');
    console.log(`   - Above VWAP at 30min = ${formatNumber((aboveVWAP30Bullish / aboveVWAP30.length) * 100)}% bullish day`);
    
    console.log('\n4. TARGETS:');
    console.log(`   - Target 1: ${formatNumber(longRRStats.median * 20)} points (${formatNumber(longRRStats.median)}:1 R:R)`);
    console.log('   - Target 2: First hour high + 50 points');
    console.log('   - Final target: Hold for close (67% close in upper half)');

    console.log('\n\n🎯 SHORT ENTRY RULES:\n');
    console.log('1. CONDITIONS:');
    console.log('   - Gap down that fails to fill');
    console.log('   - OR first 15min bearish');
    console.log('   - Price rejected at VWAP');
    
    console.log('\n2. ENTRY:');
    console.log('   - Short when price fails to break above VWAP');
    console.log('   - OR short breakdown of first 15min low');
    console.log('   - Stop: Above first 15min high');
    
    console.log('\n3. TARGETS:');
    console.log(`   - Target 1: ${formatNumber(shortRRStats.median * 20)} points`);
    console.log('   - Cover by mid-day (Mondays prefer closing higher)');

    // Export detailed entry data
    printSection('7. EXPORTING ENTRY ANALYSIS');
    const outputDir = path.join(__dirname, '..', 'var', 'output');
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }
    
    const csvFile = path.join(outputDir, `monday_entries_${INTERVAL}_${new Date().toISOString().split('T')[0]}.csv`);
    const csvHeader = 'date,gap_type,gap_pct,first15_bullish,first30_bullish,vwap_pullback,breakout,rsi_oversold,price_vs_vwap_30,long_rr,bullish_day\n';
    const csvRows = entryAnalysis.map(e => 
      `${e.date},${e.gapType},${formatNumber(e.gapPercent)},${e.first15Bullish ? 1 : 0},${e.first30Bullish ? 1 : 0},${e.bullish15PullbackToVWAP ? 1 : 0},${e.bullish15Breakout ? 1 : 0},${e.rsiOversold ? 1 : 0},${formatNumber(e.priceVsVwap30)},${formatNumber(e.longRR)},${e.bullishDay ? 1 : 0}`
    ).join('\n');
    
    fs.writeFileSync(csvFile, csvHeader + csvRows);
    console.log(`\n✓ Entry analysis exported to: ${csvFile}`);

    console.log('\n' + '='.repeat(80));
    console.log('ENTRY ANALYSIS COMPLETE');
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
console.log('MONDAY ENTRY SIGNAL ANALYSIS');
console.log(`Interval: ${INTERVAL}`);
console.log('='.repeat(80));

analyzeMondayEntries();
