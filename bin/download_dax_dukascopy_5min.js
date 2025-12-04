#!/usr/bin/env node

/**
 * Download DAX 5-minute OHLC data from Dukascopy and upload to MongoDB
 * 
 * Usage:
 *   node bin/download_dax_dukascopy.js --start 2024-01-01 --end 2024-12-31
 *   node bin/download_dax_dukascopy.js --date 2024-11-14
 *   node bin/download_dax_dukascopy.js --year 2024
 *   node bin/download_dax_dukascopy.js --daily (downloads yesterday's data)
 *   node bin/download_dax_dukascopy.js (same as --daily, for crontab)
 * 
 * Requirements:
 *   npm install dukascopy-node mongodb
 * 
 * Crontab setup (run daily at 1 AM):
 *   0 1 * * * /usr/bin/node /path/to/bin/download_dax_dukascopy.js >> /var/log/dax-download.log 2>&1
 */

const { getHistoricalRates } = require('dukascopy-node');
const { MongoClient } = require('mongodb');
const fs = require('fs');
const path = require('path');

// Load MongoDB configuration from secure config file
const CONFIG_PATH = path.join(__dirname, '..', 'etc', 'mongodb_config.json');
if (!fs.existsSync(CONFIG_PATH)) {
  console.error('ERROR: MongoDB config file not found at:', CONFIG_PATH);
  console.error('Please create etc/mongodb_config.json from etc/mongodb_config.json.template');
  process.exit(1);
}
const config = JSON.parse(fs.readFileSync(CONFIG_PATH, 'utf8'));
const MONGODB_URI = config.connection_string;
const DATABASE_NAME = config.database || 'dax_trading';
const COLLECTION_NAME = 'ohlc_5min';

// Dukascopy instrument for DAX (Germany 40)
const INSTRUMENT = 'deuidxeur';

// Log file path (for crontab execution)
const LOG_DIR = process.platform === 'win32' ? 'D:\\logs' : '/var/log';
const LOG_FILE = path.join(LOG_DIR, 'dax-download.log');

// Logging utility
function log(message, level = 'INFO') {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] [${level}] ${message}`;
  
  // Console output
  console.log(logMessage);
  
  // File output (ensure directory exists)
  try {
    if (!fs.existsSync(LOG_DIR)) {
      fs.mkdirSync(LOG_DIR, { recursive: true });
    }
    fs.appendFileSync(LOG_FILE, logMessage + '\n');
  } catch (error) {
    console.error(`Failed to write to log file: ${error.message}`);
  }
}

function logError(message, error) {
  const errorDetails = error ? ` - ${error.message}\n${error.stack}` : '';
  log(`${message}${errorDetails}`, 'ERROR');
}

function logSuccess(message) {
  log(message, 'SUCCESS');
}

function logWarning(message) {
  log(message, 'WARNING');
}

/**
 * Check if data already exists for a date
 */
async function checkExistingData(dateStr) {
  const client = new MongoClient(MONGODB_URI, {
    serverSelectionTimeoutMS: 30000,
    socketTimeoutMS: 30000,
  });

  try {
    await client.connect();
    const db = client.db(DATABASE_NAME);
    const collection = db.collection(COLLECTION_NAME);
    
    const count = await collection.countDocuments({
      session_date: dateStr
    });
    
    return count;
  } catch (error) {
    logError('Error checking existing data', error);
    return 0;
  } finally {
    await client.close();
  }
}

/**
 * Download OHLC data from Dukascopy for a date range
 */
async function downloadDukascopyData(startDate, endDate) {
  try {
    log(`Downloading DAX data from Dukascopy...`);
    log(`  Instrument: ${INSTRUMENT}`);
    log(`  Period: ${startDate.toISOString()} to ${endDate.toISOString()}`);
    log(`  Timeframe: 5 minutes`);

    const data = await getHistoricalRates({
      instrument: INSTRUMENT,
      dates: {
        from: startDate,
        to: endDate
      },
      timeframe: 'm5', // 5-minute candles
      priceType: 'bid', // Use bid prices
      utcOffset: 0,
      volumes: true,
      ignoreFlats: true,
      format: 'array' // Get array format
    });

    if (!data || data.length === 0) {
      logWarning('No data available for this period');
      return [];
    }

    logSuccess(`Downloaded ${data.length} candles`);
    
    // Transform data to match our schema
    // Array format: [timestamp, open, high, low, close, volume]
    const transformed = data.map(candle => ({
      timestamp: new Date(candle[0]),
      session_date: new Date(candle[0]).toISOString().split('T')[0],
      open: candle[1],
      high: candle[2],
      low: candle[3],
      close: candle[4],
      volume: candle[5] || 0,
      symbol: 'DE30EUR',
      interval: '5m'
    }));

    return transformed;

  } catch (error) {
    logError('Error downloading data from Dukascopy', error);
    throw error;
  }
}

/**
 * Upload data to MongoDB
 */
async function uploadToMongoDB(data) {
  if (!data || data.length === 0) {
    console.log('\n  No data to upload');
    return;
  }

  let client;
  
  try {
    console.log('\nConnecting to MongoDB...');
    client = new MongoClient(MONGODB_URI, {
      serverSelectionTimeoutMS: 30000,
      connectTimeoutMS: 30000,
      socketTimeoutMS: 30000
    });

    await client.connect();
    console.log(`  ✓ Connected to MongoDB: ${DATABASE_NAME}`);

    const db = client.db(DATABASE_NAME);
    const collection = db.collection(COLLECTION_NAME);

    // Create indexes
    console.log('\nCreating indexes...');
    await collection.createIndex({ timestamp: 1, interval: 1 }, { unique: true });
    await collection.createIndex({ session_date: 1 });
    console.log('  ✓ Indexes created');

    // Upload data with upsert
    console.log(`\nUploading ${data.length} candles to MongoDB...`);
    
    const bulkOps = data.map(doc => ({
      updateOne: {
        filter: { timestamp: doc.timestamp, interval: doc.interval },
        update: { $set: doc },
        upsert: true
      }
    }));

    const result = await collection.bulkWrite(bulkOps, { ordered: false });
    
    console.log(`  ✓ Upload complete:`);
    console.log(`    - Inserted: ${result.upsertedCount}`);
    console.log(`    - Modified: ${result.modifiedCount}`);
    console.log(`    - Total: ${data.length}`);

  } catch (error) {
    console.error(`  ✗ Error uploading to MongoDB: ${error.message}`);
    throw error;
  } finally {
    if (client) {
      await client.close();
      console.log('\n  ✓ MongoDB connection closed');
    }
  }
}

/**
 * Download data for a single date
 */
async function downloadDate(dateStr) {
  const date = new Date(dateStr);
  const nextDate = new Date(date);
  nextDate.setDate(nextDate.getDate() + 1);

  console.log('='.repeat(80));
  console.log(`Downloading DAX data for ${dateStr}`);
  console.log('='.repeat(80));

  const data = await downloadDukascopyData(date, nextDate);
  await uploadToMongoDB(data);
}

/**
 * Download data for a date range
 */
async function downloadDateRange(startStr, endStr) {
  const startDate = new Date(startStr);
  const endDate = new Date(endStr);

  console.log('='.repeat(80));
  console.log(`Downloading DAX data from ${startStr} to ${endStr}`);
  console.log('='.repeat(80));

  // Download in monthly chunks to avoid overwhelming the API
  const chunks = [];
  let currentStart = new Date(startDate);
  
  while (currentStart < endDate) {
    const currentEnd = new Date(currentStart);
    currentEnd.setMonth(currentEnd.getMonth() + 1);
    
    if (currentEnd > endDate) {
      chunks.push({ start: new Date(currentStart), end: new Date(endDate) });
    } else {
      chunks.push({ start: new Date(currentStart), end: new Date(currentEnd) });
    }
    
    currentStart = new Date(currentEnd);
  }

  console.log(`\nDownloading ${chunks.length} chunks...\n`);

  let totalCandles = 0;
  
  for (let i = 0; i < chunks.length; i++) {
    const chunk = chunks[i];
    const startStr = chunk.start.toISOString().split('T')[0];
    const endStr = chunk.end.toISOString().split('T')[0];
    
    console.log(`\n[${i + 1}/${chunks.length}] Chunk: ${startStr} to ${endStr}`);
    
    try {
      const data = await downloadDukascopyData(chunk.start, chunk.end);
      
      if (data.length > 0) {
        await uploadToMongoDB(data);
        totalCandles += data.length;
      }
      
      // Rate limiting: wait 1 second between chunks
      if (i < chunks.length - 1) {
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      
    } catch (error) {
      console.error(`  ✗ Error processing chunk: ${error.message}`);
      // Continue with next chunk
    }
  }

  console.log('\n' + '='.repeat(80));
  console.log('Download Summary');
  console.log('='.repeat(80));
  console.log(`Total candles downloaded: ${totalCandles.toLocaleString()}`);
  console.log('='.repeat(80));
}

/**
 * Download data for a full year
 */
async function downloadYear(year) {
  const startStr = `${year}-01-01`;
  const endStr = `${year}-12-31`;
  await downloadDateRange(startStr, endStr);
}

/**
 * Download yesterday's data (for daily crontab execution)
 */
async function downloadYesterday() {
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  const dateStr = yesterday.toISOString().split('T')[0];
  
  log('='.repeat(75));
  log('DAILY AUTOMATED DOWNLOAD');
  log(`Downloading yesterday's data: ${dateStr}`);
  log('='.repeat(75));
  
  // Check if data already exists
  const existingCount = await checkExistingData(dateStr);
  if (existingCount > 0) {
    logWarning(`Data for ${dateStr} already exists (${existingCount} records). Skipping download.`);
    log(`Use --date ${dateStr} to force re-download.`);
    return;
  }
  
  await downloadDate(dateStr);
}

/**
 * Main function
 */
async function main() {
  const args = process.argv.slice(2);
  const startTime = new Date();

  try {
    log('='.repeat(75));
    log('DAX DATA DOWNLOAD SCRIPT STARTED');
    log(`Script: ${__filename}`);
    log(`Platform: ${process.platform}`);
    log(`Node Version: ${process.version}`);
    log(`Working Directory: ${process.cwd()}`);
    log(`Arguments: ${args.join(' ') || '(none - daily mode)'}`);
    log('='.repeat(75));
  
  // Parse arguments
  let startDate, endDate, dateStr, year;
  
  // If no arguments or --daily, run in daily mode (download yesterday's data)
  if (args.length === 0 || args.includes('--daily')) {
    await downloadYesterday();
  } else {
    for (let i = 0; i < args.length; i++) {
      if (args[i] === '--start' && args[i + 1]) {
        startDate = args[i + 1];
      } else if (args[i] === '--end' && args[i + 1]) {
        endDate = args[i + 1];
      } else if (args[i] === '--date' && args[i + 1]) {
        dateStr = args[i + 1];
      } else if (args[i] === '--year' && args[i + 1]) {
        year = parseInt(args[i + 1]);
      }
    }

    try {
      if (year) {
        await downloadYear(year);
      } else if (dateStr) {
        await downloadDate(dateStr);
      } else if (startDate && endDate) {
        await downloadDateRange(startDate, endDate);
      } else {
        log('Usage:');
        log('  (no args)               Download yesterday\'s data (for crontab)');
        log('  --daily                 Same as no args');
        log('  --date YYYY-MM-DD       Download specific date');
        log('  --start YYYY-MM-DD --end YYYY-MM-DD    Download date range');
        log('  --year YYYY             Download entire year');
        log('');
        log('Crontab setup (daily at 1 AM):');
        log('  0 1 * * * /usr/bin/node ' + __filename + ' >> /var/log/dax-download.log 2>&1');
        process.exit(1);
      }
    } catch (innerError) {
      throw innerError;
    }
  }

    const endTime = new Date();
    const durationSeconds = ((endTime - startTime) / 1000).toFixed(2);
    
    log('='.repeat(75));
    logSuccess('SCRIPT COMPLETED SUCCESSFULLY');
    log(`Duration: ${durationSeconds} seconds`);
    log(`Completed at: ${endTime.toISOString()}`);
    log('='.repeat(75));
    process.exit(0);
    
  } catch (error) {
    const endTime = new Date();
    const durationSeconds = ((endTime - startTime) / 1000).toFixed(2);
    
    log('='.repeat(75));
    logError('SCRIPT FAILED', error);
    log(`Duration: ${durationSeconds} seconds`);
    log(`Failed at: ${endTime.toISOString()}`);
    log('='.repeat(75));
    process.exit(1);
  }
}

// Run main function
if (require.main === module) {
  main();
}

module.exports = { downloadDukascopyData, uploadToMongoDB };
