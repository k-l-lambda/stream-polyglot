#!/usr/bin/env node

import { Command } from 'commander';
import fs from 'fs/promises';
import path from 'path';
import dotenv from 'dotenv';
import { parseSRT, generateSRT, isBilingual } from './parsers/srt-parser.js';
import { SubtitleRefiner } from './refiners/llm-refiner.js';
import { createProvider } from './refiners/providers/factory.js';
import { logger } from './utils/logger.js';
import { RefinerConfig } from './types.js';

// Load environment variables
dotenv.config();

const program = new Command();

program
  .name('subtitle-refiner')
  .description('LLM-powered SRT subtitle refinement with function calling')
  .version('2.0.0')
  .argument('<input>', 'Input SRT file path')
  .option('-o, --output <file>', 'Output file path (default: input.refined.srt)')
  .option(
    '-p, --provider <name>',
    'LLM provider (currently only "openai" supported)',
    process.env.LLM_PROVIDER || 'openai'
  )
  .option('-m, --model <name>', 'Model name (e.g., gpt-4-turbo-preview, gpt-4)')
  .option(
    '-w, --window-size <number>',
    'Window size (number of subtitle entries)',
    process.env.WINDOW_SIZE || '10'
  )
  .option(
    '--max-retries <number>',
    'Maximum retries when LLM makes no progress',
    '3'
  )
  .option('--dry-run', 'Preview windows without calling LLM', false)
  .option('--verbose', 'Show detailed processing logs', false)
  .action(async (inputFile: string, options) => {
    try {
      // Set verbose mode
      if (options.verbose) {
        logger.setVerbose(true);
      }

      // Validate input file
      const inputPath = path.resolve(inputFile);
      try {
        await fs.access(inputPath);
      } catch {
        logger.error(`Input file not found: ${inputPath}`);
        process.exit(1);
      }

      // Determine output path
      const outputPath = options.output
        ? path.resolve(options.output)
        : inputPath.replace(/\.srt$/, '.refined.srt');

      logger.header('Subtitle Refiner v2.0');
      logger.info(`Input: ${inputPath}`);
      logger.info(`Output: ${outputPath}`);
      logger.info(`Provider: ${options.provider}`);

      // Read input file
      logger.info('Reading input file...');
      const content = await fs.readFile(inputPath, 'utf-8');
      const subtitles = parseSRT(content);

      if (subtitles.length === 0) {
        logger.error('No subtitles found in input file');
        process.exit(1);
      }

      logger.success(`Parsed ${subtitles.length} subtitle entries`);

      // Detect bilingual format
      const bilingual = isBilingual(subtitles);
      if (bilingual) {
        logger.info('Detected bilingual subtitles (2 lines per entry)');
      }
      logger.separator();

      // Create refiner configuration
      const config: RefinerConfig = {
        provider: options.provider,
        model: options.model,
        windowSize: parseInt(options.windowSize, 10),
        dryRun: options.dryRun,
        verbose: options.verbose,
        maxRetries: parseInt(options.maxRetries, 10),
      };

      // Create LLM provider (skip in dry-run mode)
      let refiner;
      if (options.dryRun) {
        // Create mock provider for dry-run
        const mockProvider = {
          getName: () => 'Dry Run (No API calls)',
          supportsFunctionCalling: () => true,
          refine: async () => [],
        };
        refiner = new SubtitleRefiner(mockProvider as any, config);
      } else {
        const provider = createProvider(options.provider, {
          openaiKey: process.env.OPENAI_API_KEY,
          openaiModel: options.model || process.env.OPENAI_MODEL,
          openaiBaseURL: process.env.OPENAI_BASE_URL,
        });
        refiner = new SubtitleRefiner(provider, config);
      }

      // Perform refinement
      const refined = await refiner.refine(subtitles);

      // Write output file (if not dry run)
      if (!options.dryRun) {
        logger.info('Writing output file...');
        const outputContent = generateSRT(refined);
        await fs.writeFile(outputPath, outputContent, 'utf-8');
        logger.success(`Refined subtitles saved to: ${outputPath}`);
      }

      logger.header('Done!');
    } catch (error) {
      if (error instanceof Error) {
        logger.error(`Error: ${error.message}`);
        if (options.verbose && error.stack) {
          console.error(error.stack);
        }
      }
      process.exit(1);
    }
  });

program.parse();
