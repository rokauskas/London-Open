#!/usr/bin/env node
/**
 * DAX Data Downloader using Dukascopy
 * 
 * Downloads historical OHLC data from Dukascopy for DAX (Germany 40 Index)
 * and outputs it as CSV or JSON.
 * 
 * Usage:
 *   node bin/download_dukascopy_data.js --from 2025-01-01 --to 2025-12-31 --timeframe m5
 *   node bin/download_dukascopy_data.js --date 2025-12-03 --timeframe m5
 * 
 * Options:
 *   --from: Start date (YYYY-MM-DD)
 *   --to: End date (YYYY-MM-DD)
 *   --date: Single date (YYYY-MM-DD) - downloads just that day
 *   --timeframe: Data timeframe (tick, s1, m1, m5, m15, m30, h1, h4, d1) - default: m5
 *   --instrument: Dukascopy instrument code - default: deuidxeur (DAX)
 *   --format: Output format (json, csv) - default: json
 *   --output: Output file path (optional)
 * 
 * Note: Uses 'ignoreFlats: false' to include all data points, even when price doesn't change
 */

const { getHistoricalRates } = require('dukascopy-node');
const fs = require('fs');
const path = require('path');

// Parse command line arguments
function parseArgs() {
  const args = process.argv.slice(2);
  const config = {
    instrument: 'deuidxeur', // DAX (Germany 40 Index)
    timeframe: 'm5',          // 5-minute candles
    format: 'json'
  };
  
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--from' && args[i + 1]) {
      config.from = args[i + 1];
      i++;
    } else if (args[i] === '--to' && args[i + 1]) {
      config.to = args[i + 1];
      i++;
    } else if (args[i] === '--date' && args[i + 1]) {
      // For single date, set both from and to
      config.from = args[i + 1];
      config.to = args[i + 1];
      i++;
    } else if (args[i] === '--timeframe' && args[i + 1]) {
      config.timeframe = args[i + 1];
      i++;
    } else if (args[i] === '--instrument' && args[i + 1]) {
      config.instrument = args[i + 1];
      i++;
    } else if (args[i] === '--format' && args[i + 1]) {
      config.format = args[i + 1];
      i++;
    } else if (args[i] === '--output' && args[i + 1]) {
      config.output = args[i + 1];
      i++;
    }
  }
  
  // Validate required arguments
  if (!config.from || !config.to) {
    console.error('Error: --from and --to dates are required (or use --date for a single day)');
    console.error('Usage: node download_dukascopy_data.js --from 2025-01-01 --to 2025-12-31 --timeframe m5');
    process.exit(1);
  }
  
  return config;
}

// Main download function
async function downloadData() {
  const config = parseArgs();
  
  console.log('Downloading DAX data from Dukascopy...');
  console.log(`Instrument: ${config.instrument}`);
  console.log(`Date range: ${config.from} to ${config.to}`);
  console.log(`Timeframe: ${config.timeframe}`);
  console.log(`Format: ${config.format}`);
  
  try {
    const data = await getHistoricalRates({
      instrument: config.instrument,
      dates: {
        from: new Date(config.from),
        to: new Date(config.to)
      },
      timeframe: config.timeframe,
      format: config.format,
      priceType: 'bid', // Use bid prices
      utcOffset: 0,     // UTC timezone
      volumes: true,    // Include volume data
      ignoreFlats: false
    });
    
    if (!data || (Array.isArray(data) && data.length === 0)) {
      console.error('Warning: No data returned. This might be a weekend, holiday, or no trading activity.');
      process.exit(1);
    }
    
    // Output results
    if (config.output) {
      // Write to file
      const outputDir = path.dirname(config.output);
      if (!fs.existsSync(outputDir)) {
        fs.mkdirSync(outputDir, { recursive: true });
      }
      
      if (config.format === 'json') {
        fs.writeFileSync(config.output, JSON.stringify(data, null, 2));
      } else {
        fs.writeFileSync(config.output, data);
      }
      
      console.log(`✓ Downloaded ${Array.isArray(data) ? data.length : 'unknown'} candles`);
      console.log(`✓ Data saved to: ${config.output}`);
    } else {
      // Output to stdout
      if (config.format === 'json') {
        console.log(JSON.stringify(data, null, 2));
      } else {
        console.log(data);
      }
    }
    
    // Exit with success
    process.exit(0);
    
  } catch (error) {
    console.error('Error downloading data:', error.message);
    if (error.response) {
      console.error('Response status:', error.response.status);
      console.error('Response data:', error.response.data);
    }
    process.exit(1);
  }
}

// Run the download
downloadData();
