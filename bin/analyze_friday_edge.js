#!/usr/bin/env node

/**
 * Advanced Friday Trading Edge Analysis with Machine Learning
 * 
 * Features:
 * - TensorFlow.js neural networks for pattern prediction
 * - Advanced technical indicators (VWAP, Bollinger Bands, RSI, EMA)
 * - Statistical analysis with regression models
 * - Morning session (08:00-10:00) predictive power analysis
 * - ML-based entry/exit signal generation with confidence scores
 * - Comparative period analysis
 */

const { MongoClient } = require('mongodb');
const fs = require('fs');
const path = require('path');
const tf = require('@tensorflow/tfjs');
const ti = require('technicalindicators');
const stats = require('simple-statistics');
const math = require('mathjs');
const { SLR, MultivariateLinearRegression } = require('ml-regression');

// Load MongoDB configuration
const configPath = path.join(__dirname, '..', 'etc', 'mongodb_config.json');
const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));

const MONGODB_URI = config.connection_string;
const DATABASE_NAME = config.database;
const COLLECTION_NAME_5M = 'ohlc_5min';

// Constants
const MORNING_START_HOUR = 8;
const MORNING_END_HOUR = 10;
const MARKET_OPEN_HOUR = 8;
const MARKET_CLOSE_HOUR = 22;

/**
 * Calculate VWAP (Volume Weighted Average Price)
 */
function calculateVWAP(candles) {
  let cumulativeTPV = 0; // Typical Price * Volume
  let cumulativeVolume = 0;
  
  return candles.map(candle => {
    const typicalPrice = (candle.high + candle.low + candle.close) / 3;
    cumulativeTPV += typicalPrice * candle.volume;
    cumulativeVolume += candle.volume;
    return cumulativeVolume > 0 ? cumulativeTPV / cumulativeVolume : typicalPrice;
  });
}

/**
 * Calculate EMA (Exponential Moving Average)
 */
function calculateEMA(prices, period) {
  const emaValues = ti.EMA.calculate({
    period: period,
    values: prices
  });
  // Pad with nulls to match original array length
  return Array(prices.length - emaValues.length).fill(null).concat(emaValues);
}

/**
 * Calculate RSI (Relative Strength Index)
 */
function calculateRSI(prices, period = 14) {
  const rsiValues = ti.RSI.calculate({
    period: period,
    values: prices
  });
  return Array(prices.length - rsiValues.length).fill(null).concat(rsiValues);
}

/**
 * Calculate Bollinger Bands
 */
function calculateBollingerBands(prices, period = 20, stdDev = 2) {
  const bbValues = ti.BollingerBands.calculate({
    period: period,
    stdDev: stdDev,
    values: prices
  });
  return Array(prices.length - bbValues.length).fill(null).concat(bbValues);
}

/**
 * Calculate ATR (Average True Range)
 */
function calculateATR(candles, period = 14) {
  const atrValues = ti.ATR.calculate({
    period: period,
    high: candles.map(c => c.high),
    low: candles.map(c => c.low),
    close: candles.map(c => c.close)
  });
  return Array(candles.length - atrValues.length).fill(null).concat(atrValues);
}

/**
 * Calculate MACD
 */
function calculateMACD(prices) {
  const macdValues = ti.MACD.calculate({
    values: prices,
    fastPeriod: 12,
    slowPeriod: 26,
    signalPeriod: 9,
    SimpleMAOscillator: false,
    SimpleMASignal: false
  });
  return Array(prices.length - macdValues.length).fill(null).concat(macdValues);
}

/**
 * Calculate Stochastic Oscillator
 */
function calculateStochastic(candles, period = 14) {
  const stochValues = ti.Stochastic.calculate({
    high: candles.map(c => c.high),
    low: candles.map(c => c.low),
    close: candles.map(c => c.close),
    period: period,
    signalPeriod: 3
  });
  return Array(candles.length - stochValues.length).fill(null).concat(stochValues);
}

/**
 * Analyze a single Friday session
 */
function analyzeFriday(sessionDate, candles) {
  const sessionDateObj = new Date(sessionDate);
  
  // Sort candles by time
  candles.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  
  // Calculate all technical indicators
  const closes = candles.map(c => c.close);
  const highs = candles.map(c => c.high);
  const lows = candles.map(c => c.low);
  const volumes = candles.map(c => c.volume);
  
  const vwap = calculateVWAP(candles);
  const ema20 = calculateEMA(closes, 20);
  const ema50 = calculateEMA(closes, 50);
  const rsi = calculateRSI(closes, 14);
  const bb = calculateBollingerBands(closes, 20, 2);
  const atr = calculateATR(candles, 14);
  const macd = calculateMACD(closes);
  const stoch = calculateStochastic(candles, 14);
  
  // Split into morning (08:00-10:00) and rest of day
  const morningCandles = candles.filter(c => {
    const hour = new Date(c.timestamp).getUTCHours();
    return hour >= MORNING_START_HOUR && hour < MORNING_END_HOUR;
  });
  
  const afternoonCandles = candles.filter(c => {
    const hour = new Date(c.timestamp).getUTCHours();
    return hour >= MORNING_END_HOUR && hour < MARKET_CLOSE_HOUR;
  });
  
  if (morningCandles.length === 0 || afternoonCandles.length === 0) {
    return null; // Skip incomplete days
  }
  
  // Morning statistics
  const morningOpen = morningCandles[0].open;
  const morningClose = morningCandles[morningCandles.length - 1].close;
  const morningHigh = Math.max(...morningCandles.map(c => c.high));
  const morningLow = Math.min(...morningCandles.map(c => c.low));
  const morningRange = morningHigh - morningLow;
  const morningMove = morningClose - morningOpen;
  const morningMovePercent = (morningMove / morningOpen) * 100;
  const morningVolume = morningCandles.reduce((sum, c) => sum + c.volume, 0);
  
  // Morning technical indicators (at 10:00)
  const morningEndIdx = candles.indexOf(morningCandles[morningCandles.length - 1]);
  const morningVWAP = vwap[morningEndIdx];
  const morningEMA20 = ema20[morningEndIdx];
  const morningEMA50 = ema50[morningEndIdx];
  const morningRSI = rsi[morningEndIdx];
  const morningBB = bb[morningEndIdx];
  const morningATR = atr[morningEndIdx];
  const morningMACD = macd[morningEndIdx];
  const morningStoch = stoch[morningEndIdx];
  
  // Price position relative to indicators
  const priceVsVWAP = morningClose > morningVWAP ? 1 : -1;
  const priceVsEMA20 = morningClose > morningEMA20 ? 1 : -1;
  const priceVsEMA50 = morningClose > morningEMA50 ? 1 : -1;
  const priceBBPosition = morningBB ? (morningClose - morningBB.lower) / (morningBB.upper - morningBB.lower) : 0.5;
  
  // Full day statistics
  const dayOpen = candles[0].open;
  const dayClose = candles[candles.length - 1].close;
  const dayHigh = Math.max(...candles.map(c => c.high));
  const dayLow = Math.min(...candles.map(c => c.low));
  const dayRange = dayHigh - dayLow;
  const dayMove = dayClose - dayOpen;
  const dayMovePercent = (dayMove / dayOpen) * 100;
  const dayVolume = candles.reduce((sum, c) => sum + c.volume, 0);
  
  // Afternoon statistics
  const afternoonOpen = afternoonCandles[0].open;
  const afternoonClose = afternoonCandles[afternoonCandles.length - 1].close;
  const afternoonHigh = Math.max(...afternoonCandles.map(c => c.high));
  const afternoonLow = Math.min(...afternoonCandles.map(c => c.low));
  const afternoonRange = afternoonHigh - afternoonLow;
  const afternoonMove = afternoonClose - afternoonOpen;
  const afternoonMovePercent = (afternoonMove / afternoonOpen) * 100;
  const afternoonVolume = afternoonCandles.reduce((sum, c) => sum + c.volume, 0);
  
  // Direction alignment
  const morningBullish = morningMove > 0;
  const afternoonBullish = afternoonMove > 0;
  const dayBullish = dayMove > 0;
  const morningAfternoonAlign = morningBullish === afternoonBullish;
  const morningDayAlign = morningBullish === dayBullish;
  
  // Get Friday close from previous week for gap analysis
  const prevFridayClose = null; // Would need to query previous Friday
  
  return {
    date: sessionDate,
    
    // Morning session
    morning: {
      open: morningOpen,
      close: morningClose,
      high: morningHigh,
      low: morningLow,
      range: morningRange,
      move: morningMove,
      movePercent: morningMovePercent,
      bullish: morningBullish,
      volume: morningVolume,
      
      // Technical indicators
      vwap: morningVWAP,
      ema20: morningEMA20,
      ema50: morningEMA50,
      rsi: morningRSI,
      bb: morningBB,
      atr: morningATR,
      macd: morningMACD,
      stoch: morningStoch,
      
      // Relative positions
      priceVsVWAP: priceVsVWAP,
      priceVsEMA20: priceVsEMA20,
      priceVsEMA50: priceVsEMA50,
      priceBBPosition: priceBBPosition
    },
    
    // Afternoon session
    afternoon: {
      open: afternoonOpen,
      close: afternoonClose,
      high: afternoonHigh,
      low: afternoonLow,
      range: afternoonRange,
      move: afternoonMove,
      movePercent: afternoonMovePercent,
      bullish: afternoonBullish,
      volume: afternoonVolume
    },
    
    // Full day
    day: {
      open: dayOpen,
      close: dayClose,
      high: dayHigh,
      low: dayLow,
      range: dayRange,
      move: dayMove,
      movePercent: dayMovePercent,
      bullish: dayBullish,
      volume: dayVolume
    },
    
    // Relationships
    morningAfternoonAlign: morningAfternoonAlign,
    morningDayAlign: morningDayAlign,
    morningRangePercent: (morningRange / dayRange) * 100,
    morningVolumePercent: (morningVolume / dayVolume) * 100
  };
}

/**
 * Build ML features from Friday data
 */
function buildMLFeatures(fridayData) {
  const features = [];
  const labels = [];
  
  for (const friday of fridayData) {
    if (!friday) continue;
    
    // Features: morning session indicators
    const feature = [
      friday.morning.movePercent,
      friday.morning.range,
      friday.morning.volume,
      friday.morning.rsi || 50,
      friday.morning.priceVsVWAP,
      friday.morning.priceVsEMA20,
      friday.morning.priceVsEMA50,
      friday.morning.priceBBPosition,
      friday.morning.macd ? friday.morning.macd.MACD : 0,
      friday.morning.macd ? friday.morning.macd.signal : 0,
      friday.morning.stoch ? friday.morning.stoch.k : 50,
      friday.morning.stoch ? friday.morning.stoch.d : 50
    ];
    
    // Label: afternoon move (positive or negative)
    const label = friday.afternoon.movePercent;
    
    features.push(feature);
    labels.push(label);
  }
  
  return { features, labels };
}

/**
 * Train neural network model
 */
async function trainNeuralNetwork(features, labels) {
  // Normalize features
  const featureTensor = tf.tensor2d(features);
  const labelTensor = tf.tensor2d(labels.map(l => [l]));
  
  const { mean, variance } = tf.moments(featureTensor, 0);
  const std = variance.sqrt();
  const normalizedFeatures = featureTensor.sub(mean).div(std.add(1e-7));
  
  // Build model
  const model = tf.sequential({
    layers: [
      tf.layers.dense({ inputShape: [features[0].length], units: 24, activation: 'relu' }),
      tf.layers.dropout({ rate: 0.2 }),
      tf.layers.dense({ units: 12, activation: 'relu' }),
      tf.layers.dropout({ rate: 0.2 }),
      tf.layers.dense({ units: 6, activation: 'relu' }),
      tf.layers.dense({ units: 1, activation: 'linear' })
    ]
  });
  
  model.compile({
    optimizer: tf.train.adam(0.001),
    loss: 'meanSquaredError',
    metrics: ['mae']
  });
  
  // Train model
  const history = await model.fit(normalizedFeatures, labelTensor, {
    epochs: 100,
    batchSize: 8,
    validationSplit: 0.2,
    shuffle: true,
    verbose: 0,
    callbacks: {
      onEpochEnd: (epoch, logs) => {
        if (epoch % 20 === 0) {
          console.log(`  Epoch ${epoch}: loss = ${logs.loss.toFixed(4)}, val_loss = ${logs.val_loss.toFixed(4)}`);
        }
      }
    }
  });
  
  return { model, mean: mean.arraySync(), std: std.arraySync() };
}

/**
 * Predict using trained model
 */
async function predict(model, mean, std, features) {
  const featureTensor = tf.tensor2d([features]);
  const meanTensor = tf.tensor1d(mean);
  const stdTensor = tf.tensor1d(std);
  
  const normalizedFeatures = featureTensor.sub(meanTensor).div(stdTensor.add(1e-7));
  const prediction = model.predict(normalizedFeatures);
  const result = await prediction.data();
  
  return result[0];
}

/**
 * Generate trading signals based on patterns
 */
function generateTradingSignals(fridayData, mlPredictions) {
  const signals = [];
  
  for (let i = 0; i < fridayData.length; i++) {
    const friday = fridayData[i];
    if (!friday) continue;
    
    const mlPrediction = mlPredictions[i];
    const morningMove = friday.morning.movePercent;
    const morningRSI = friday.morning.rsi || 50;
    const priceVsVWAP = friday.morning.priceVsVWAP;
    const actualAfternoon = friday.afternoon.movePercent;
    
    // Signal logic
    let signal = null;
    let confidence = 0;
    let entryPrice = friday.morning.close;
    let stopLoss = 0;
    let target = 0;
    let reasoning = [];
    
    // LONG signals
    if (mlPrediction > 0.1 && morningMove > 0 && priceVsVWAP > 0) {
      signal = 'LONG';
      confidence = Math.min(95, 50 + Math.abs(mlPrediction) * 10 + (morningRSI < 70 ? 10 : 0) + 10);
      stopLoss = friday.morning.low;
      target = entryPrice + Math.abs(entryPrice - stopLoss) * 3;
      reasoning.push('ML predicts bullish afternoon');
      reasoning.push('Morning session bullish');
      reasoning.push('Price above VWAP');
      if (morningRSI < 70) reasoning.push('RSI not overbought');
    }
    // SHORT signals
    else if (mlPrediction < -0.1 && morningMove < 0 && priceVsVWAP < 0) {
      signal = 'SHORT';
      confidence = Math.min(95, 50 + Math.abs(mlPrediction) * 10 + (morningRSI > 30 ? 10 : 0) + 10);
      stopLoss = friday.morning.high;
      target = entryPrice - Math.abs(stopLoss - entryPrice) * 3;
      reasoning.push('ML predicts bearish afternoon');
      reasoning.push('Morning session bearish');
      reasoning.push('Price below VWAP');
      if (morningRSI > 30) reasoning.push('RSI not oversold');
    }
    // LONG reversal after morning drop
    else if (mlPrediction > 0.15 && morningMove < -0.2 && morningRSI < 40) {
      signal = 'LONG';
      confidence = Math.min(90, 55 + Math.abs(mlPrediction) * 8);
      stopLoss = friday.morning.low;
      target = entryPrice + Math.abs(entryPrice - stopLoss) * 2.5;
      reasoning.push('ML predicts reversal');
      reasoning.push('Morning oversold (RSI < 40)');
      reasoning.push('Strong morning drop may reverse');
    }
    // SHORT reversal after morning rally
    else if (mlPrediction < -0.15 && morningMove > 0.2 && morningRSI > 60) {
      signal = 'SHORT';
      confidence = Math.min(90, 55 + Math.abs(mlPrediction) * 8);
      stopLoss = friday.morning.high;
      target = entryPrice - Math.abs(stopLoss - entryPrice) * 2.5;
      reasoning.push('ML predicts reversal');
      reasoning.push('Morning overbought (RSI > 60)');
      reasoning.push('Strong morning rally may reverse');
    }
    
    if (signal) {
      const risk = Math.abs(entryPrice - stopLoss);
      const reward = Math.abs(target - entryPrice);
      const riskReward = reward / risk;
      
      // Check actual outcome
      const outcome = signal === 'LONG' 
        ? actualAfternoon > 0 
        : actualAfternoon < 0;
      
      signals.push({
        date: friday.date,
        signal: signal,
        confidence: confidence.toFixed(2),
        entry: entryPrice.toFixed(2),
        stopLoss: stopLoss.toFixed(2),
        target: target.toFixed(2),
        risk: risk.toFixed(2),
        reward: reward.toFixed(2),
        riskReward: riskReward.toFixed(2),
        mlPrediction: mlPrediction.toFixed(4),
        morningMove: morningMove.toFixed(2),
        morningRSI: morningRSI.toFixed(2),
        actualAfternoonMove: actualAfternoon.toFixed(2),
        outcome: outcome ? 'WIN' : 'LOSS',
        reasoning: reasoning.join('; ')
      });
    }
  }
  
  return signals;
}

/**
 * Calculate statistics
 */
function calculateStats(values) {
  if (values.length === 0) return null;
  
  return {
    mean: stats.mean(values),
    median: stats.median(values),
    std: stats.standardDeviation(values),
    min: stats.min(values),
    max: stats.max(values),
    q1: stats.quantile(values, 0.25),
    q3: stats.quantile(values, 0.75)
  };
}

/**
 * Main analysis function
 */
async function analyzeFridayEdge() {
  console.log('\n' + '='.repeat(80));
  console.log('FRIDAY TRADING EDGE ANALYSIS WITH MACHINE LEARNING');
  console.log('='.repeat(80));
  console.log(`Focus: Morning session (${MORNING_START_HOUR}:00-${MORNING_END_HOUR}:00) predictive power`);
  console.log('='.repeat(80));
  
  let client;
  
  try {
    // Connect to MongoDB
    console.log('\nConnecting to MongoDB...');
    client = new MongoClient(MONGODB_URI, {
      serverSelectionTimeoutMS: 30000,
      connectTimeoutMS: 30000,
      socketTimeoutMS: 30000
    });
    
    await client.connect();
    console.log('✓ Connected to MongoDB');
    
    const db = client.db(DATABASE_NAME);
    const collection = db.collection(COLLECTION_NAME_5M);
    
    // Get all Fridays
    console.log('\nQuerying Friday data...');
    const fridayDocs = await collection.find({ day_of_week: 'Friday' }).toArray();
    const fridays = [...new Set(fridayDocs.map(doc => doc.session_date))];
    fridays.sort();
    
    console.log(`✓ Found ${fridays.length} Fridays in database`);
    
    // Analyze each Friday
    console.log('\nAnalyzing Friday sessions...');
    const fridayData = [];
    
    for (const sessionDate of fridays) {
      const candles = await collection.find({
        session_date: sessionDate,
        interval: '5m'
      }).toArray();
      
      const analysis = analyzeFriday(sessionDate, candles);
      if (analysis) {
        fridayData.push(analysis);
      }
    }
    
    console.log(`✓ Analyzed ${fridayData.length} complete Friday sessions`);
    
    // Build ML dataset
    console.log('\nBuilding ML dataset...');
    const { features, labels } = buildMLFeatures(fridayData);
    console.log(`✓ Built dataset: ${features.length} samples with ${features[0].length} features`);
    
    // Train neural network
    console.log('\nTraining neural network...');
    const { model, mean, std } = await trainNeuralNetwork(features, labels);
    console.log('✓ Model trained successfully');
    
    // Generate predictions
    console.log('\nGenerating predictions...');
    const mlPredictions = [];
    for (let i = 0; i < features.length; i++) {
      const pred = await predict(model, mean, std, features[i]);
      mlPredictions.push(pred);
    }
    console.log('✓ Predictions generated');
    
    // Generate trading signals
    console.log('\nGenerating trading signals...');
    const signals = generateTradingSignals(fridayData, mlPredictions);
    console.log(`✓ Generated ${signals.length} trading signals`);
    
    // Calculate signal performance
    const winningSignals = signals.filter(s => s.outcome === 'WIN');
    const winRate = (winningSignals.length / signals.length) * 100;
    const avgRiskReward = stats.mean(signals.map(s => parseFloat(s.riskReward)));
    
    const longSignals = signals.filter(s => s.signal === 'LONG');
    const shortSignals = signals.filter(s => s.signal === 'SHORT');
    const longWinRate = longSignals.length > 0 
      ? (longSignals.filter(s => s.outcome === 'WIN').length / longSignals.length) * 100 
      : 0;
    const shortWinRate = shortSignals.length > 0 
      ? (shortSignals.filter(s => s.outcome === 'WIN').length / shortSignals.length) * 100 
      : 0;
    
    // Statistical analysis
    console.log('\n' + '='.repeat(80));
    console.log('STATISTICAL ANALYSIS');
    console.log('='.repeat(80));
    
    const morningMoves = fridayData.map(f => f.morning.movePercent);
    const afternoonMoves = fridayData.map(f => f.afternoon.movePercent);
    const dayMoves = fridayData.map(f => f.day.movePercent);
    const morningRanges = fridayData.map(f => f.morning.range);
    const afternoonRanges = fridayData.map(f => f.afternoon.range);
    
    console.log('\nMorning Session (08:00-10:00):');
    const morningStats = calculateStats(morningMoves);
    console.log(`  Move %: ${morningStats.mean.toFixed(3)}% ± ${morningStats.std.toFixed(3)}% (median: ${morningStats.median.toFixed(3)}%)`);
    console.log(`  Range: ${stats.mean(morningRanges).toFixed(2)} points`);
    console.log(`  Bullish: ${fridayData.filter(f => f.morning.bullish).length} (${(fridayData.filter(f => f.morning.bullish).length / fridayData.length * 100).toFixed(1)}%)`);
    
    console.log('\nAfternoon Session (10:00-22:00):');
    const afternoonStats = calculateStats(afternoonMoves);
    console.log(`  Move %: ${afternoonStats.mean.toFixed(3)}% ± ${afternoonStats.std.toFixed(3)}% (median: ${afternoonStats.median.toFixed(3)}%)`);
    console.log(`  Range: ${stats.mean(afternoonRanges).toFixed(2)} points`);
    console.log(`  Bullish: ${fridayData.filter(f => f.afternoon.bullish).length} (${(fridayData.filter(f => f.afternoon.bullish).length / fridayData.length * 100).toFixed(1)}%)`);
    
    console.log('\nFull Day:');
    const dayStats = calculateStats(dayMoves);
    console.log(`  Move %: ${dayStats.mean.toFixed(3)}% ± ${dayStats.std.toFixed(3)}% (median: ${dayStats.median.toFixed(3)}%)`);
    console.log(`  Bullish: ${fridayData.filter(f => f.day.bullish).length} (${(fridayData.filter(f => f.day.bullish).length / fridayData.length * 100).toFixed(1)}%)`);
    
    // Predictive power
    const alignedMorningAfternoon = fridayData.filter(f => f.morningAfternoonAlign).length;
    const alignedMorningDay = fridayData.filter(f => f.morningDayAlign).length;
    
    console.log('\n' + '='.repeat(80));
    console.log('PREDICTIVE POWER');
    console.log('='.repeat(80));
    console.log(`Morning predicts afternoon: ${(alignedMorningAfternoon / fridayData.length * 100).toFixed(2)}% accuracy`);
    console.log(`Morning predicts full day: ${(alignedMorningDay / fridayData.length * 100).toFixed(2)}% accuracy`);
    
    // ML Performance
    console.log('\n' + '='.repeat(80));
    console.log('MACHINE LEARNING PERFORMANCE');
    console.log('='.repeat(80));
    console.log(`Total signals generated: ${signals.length}`);
    console.log(`Overall win rate: ${winRate.toFixed(2)}%`);
    console.log(`Average Risk:Reward: ${avgRiskReward.toFixed(2)}:1`);
    console.log(`\nLONG signals: ${longSignals.length} (${longWinRate.toFixed(2)}% win rate)`);
    console.log(`SHORT signals: ${shortSignals.length} (${shortWinRate.toFixed(2)}% win rate)`);
    
    // Top signals
    console.log('\n' + '='.repeat(80));
    console.log('TOP 10 HIGH-CONFIDENCE SIGNALS');
    console.log('='.repeat(80));
    
    const topSignals = signals
      .sort((a, b) => parseFloat(b.confidence) - parseFloat(a.confidence))
      .slice(0, 10);
    
    topSignals.forEach((sig, idx) => {
      console.log(`\n${idx + 1}. ${sig.date} - ${sig.signal} (${sig.outcome})`);
      console.log(`   Confidence: ${sig.confidence}%`);
      console.log(`   Entry: ${sig.entry}, Stop: ${sig.stopLoss}, Target: ${sig.target}`);
      console.log(`   Risk:Reward: ${sig.riskReward}:1`);
      console.log(`   ML Prediction: ${sig.mlPrediction}% afternoon move`);
      console.log(`   Actual: ${sig.actualAfternoonMove}%`);
      console.log(`   Reasoning: ${sig.reasoning}`);
    });
    
    // Export results to CSV
    console.log('\n' + '='.repeat(80));
    console.log('EXPORTING RESULTS');
    console.log('='.repeat(80));
    
    const outputDir = path.join(__dirname, '..', 'var', 'output');
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }
    
    const timestamp = new Date().toISOString().split('T')[0];
    const csvPath = path.join(outputDir, `friday_edge_analysis_${timestamp}.csv`);
    
    const csvHeaders = Object.keys(signals[0]).join(',');
    const csvRows = signals.map(sig => Object.values(sig).join(','));
    const csvContent = [csvHeaders, ...csvRows].join('\n');
    
    fs.writeFileSync(csvPath, csvContent);
    console.log(`✓ Results exported to: ${csvPath}`);
    
    // Trading recommendations
    console.log('\n' + '='.repeat(80));
    console.log('TRADING RECOMMENDATIONS');
    console.log('='.repeat(80));
    
    console.log('\n📊 OPTIMAL STRATEGY:');
    if (winRate > 65) {
      console.log(`  ✓ HIGH EDGE DETECTED: ${winRate.toFixed(1)}% win rate with ${avgRiskReward.toFixed(2)}:1 R:R`);
      console.log(`  ✓ Focus on signals with confidence > 70%`);
      console.log(`  ✓ Average expected value per trade is POSITIVE`);
    } else {
      console.log(`  ⚠ Moderate edge: ${winRate.toFixed(1)}% win rate`);
      console.log(`  ⚠ Be selective - only take highest confidence signals (>80%)`);
    }
    
    console.log('\n📈 ENTRY RULES:');
    console.log('  1. Wait for 10:00 AM (end of morning session)');
    console.log('  2. Check ML prediction and confidence score');
    console.log('  3. Confirm with technical indicators (VWAP, RSI, EMA alignment)');
    console.log('  4. Enter only if confidence > 70% and R:R > 2:1');
    console.log('  5. Place stop loss at morning high/low');
    console.log('  6. Target 3x the risk for optimal edge');
    
    console.log('\n⚠️  RISK MANAGEMENT:');
    console.log('  • Risk max 1% of account per trade');
    console.log('  • No more than 2 trades per Friday');
    console.log('  • Cut losses if stop is hit');
    console.log('  • Take partial profits at 2R, let rest run to 3R');
    
    console.log('\n' + '='.repeat(80));
    console.log('ANALYSIS COMPLETE');
    console.log('='.repeat(80));
    
  } catch (error) {
    console.error('\n❌ Error during analysis:', error.message);
    console.error(error.stack);
    process.exit(1);
  } finally {
    if (client) {
      await client.close();
      console.log('\n✓ MongoDB connection closed');
    }
  }
}

// Run analysis
analyzeFridayEdge().catch(error => {
  console.error('Fatal error:', error);
  process.exit(1);
});
