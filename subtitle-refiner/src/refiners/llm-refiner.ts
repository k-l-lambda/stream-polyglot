import { LLMProvider, RefinerConfig, ProcessingStats, Subtitle } from '../types.js';
import { SubtitleStateManager } from '../utils/state-manager.js';
import { createCenteredWindow, formatWindowDisplay } from '../utils/window.js';
import { logger } from '../utils/logger.js';
import { DEFAULT_SYSTEM_PROMPT } from '../prompts/default-prompts.js';

export class SubtitleRefiner {
  private provider: LLMProvider;
  private config: RefinerConfig;
  private systemPrompt: string;
  private stats: ProcessingStats;

  constructor(provider: LLMProvider, config: RefinerConfig) {
    this.provider = provider;
    this.config = config;
    this.systemPrompt = DEFAULT_SYSTEM_PROMPT;
    this.stats = {
      totalSubtitles: 0,
      finishedSubtitles: 0,
      refinedSubtitles: 0,
      rounds: 0,
      noProgressRounds: 0,
      llmCalls: 0,
    };

    // Verify provider supports function calling
    if (!provider.supportsFunctionCalling()) {
      throw new Error(`Provider ${provider.getName()} does not support function calling`);
    }
  }

  /**
   * Refine all subtitles using centered window strategy with function calling
   */
  async refine(subtitles: Subtitle[]): Promise<Subtitle[]> {
    if (subtitles.length === 0) {
      logger.warn('No subtitles to refine');
      return subtitles;
    }

    logger.header('Subtitle Refiner with Function Calling');
    logger.info(`Provider: ${this.provider.getName()}`);
    logger.info(`Window size: ${this.config.windowSize}`);
    logger.info(`Total subtitles: ${subtitles.length}`);
    logger.separator();

    // Initialize state manager
    const stateManager = new SubtitleStateManager(subtitles);
    this.stats.totalSubtitles = subtitles.length;

    if (this.config.dryRun) {
      return this.dryRun(stateManager);
    }

    // Main processing loop
    let round = 0;
    let previousFirstUnfinished = -1;

    while (!stateManager.isAllFinished()) {
      round++;
      this.stats.rounds = round;

      // Create centered window
      const window = createCenteredWindow(stateManager, this.config.windowSize);

      if (!window) {
        break; // All finished
      }

      logger.header(`Round ${round}`);
      logger.info(formatWindowDisplay(window));
      logger.separator();

      // Check if stuck (no progress from last round)
      const isStuck = window.firstUnfinishedIndex === previousFirstUnfinished;
      if (isStuck) {
        this.stats.noProgressRounds++;
        logger.warn(`No progress detected (still at #${window.firstUnfinishedIndex})`);

        // Fail if stuck too long
        if (this.stats.noProgressRounds >= this.config.maxRetries) {
          logger.error(`Failed after ${this.config.maxRetries} attempts with no progress`);
          logger.error('LLM is not calling functions properly');
          throw new Error(
            `Refinement failed: No progress after ${this.config.maxRetries} rounds`
          );
        }
      } else {
        this.stats.noProgressRounds = 0; // Reset counter when progress is made
      }

      // Call LLM with retry prompt if stuck
      const retryPrompt = isStuck ? 'RETRY' : undefined;

      try {
        this.stats.llmCalls++;
        const functionCalls = await this.provider.refine(
          window,
          this.systemPrompt,
          retryPrompt
        );

        // Process function calls
        let processedCount = 0;

        for (const call of functionCalls) {
          const success = this.processFunctionCall(stateManager, call);
          if (success) processedCount++;
        }

        logger.success(`Processed ${processedCount} function calls`);

        // Update stats
        this.stats.finishedSubtitles = stateManager.getFinishedCount();
        this.stats.refinedSubtitles = stateManager.getRefinedCount();

        logger.info(
          `Progress: ${this.stats.finishedSubtitles}/${this.stats.totalSubtitles} finished`
        );
        logger.separator();

        // Update previous position
        previousFirstUnfinished = window.firstUnfinishedIndex;

        // Brief delay to avoid rate limits
        await this.sleep(500);
      } catch (error) {
        logger.error(`Error in round ${round}`);
        if (error instanceof Error) {
          logger.error(error.message);
        }
        throw error;
      }
    }

    // Final summary
    this.printSummary();

    return stateManager.export();
  }

  /**
   * Process a single function call
   */
  private processFunctionCall(
    stateManager: SubtitleStateManager,
    call: any
  ): boolean {
    const id = call.arguments?.id;

    if (!id || typeof id !== 'number') {
      logger.warn(`Invalid function call: missing or invalid id`);
      return false;
    }

    if (call.name === 'this_is_fine') {
      const success = stateManager.markFine(id);
      if (success) {
        logger.debug(`✓ Marked #${id} as fine`);
      } else {
        logger.warn(`Failed to mark #${id} (not found)`);
      }
      return success;
    } else if (call.name === 'this_should_be') {
      const tarText = call.arguments?.tar_text;
      const srcText = call.arguments?.src_text;

      if (!tarText || !srcText) {
        logger.warn(`Invalid this_should_be call for #${id}: missing text`);
        return false;
      }

      const success = stateManager.markRefined(id, srcText, tarText);
      if (success) {
        logger.debug(`✓ Refined #${id}`);
      } else {
        logger.warn(`Failed to refine #${id} (not found)`);
      }
      return success;
    }

    logger.warn(`Unknown function: ${call.name}`);
    return false;
  }

  /**
   * Dry run mode - show windows without calling LLM
   */
  private dryRun(stateManager: SubtitleStateManager): Subtitle[] {
    logger.header('Dry Run Mode');
    logger.info('Showing windows without calling LLM\n');

    let round = 0;

    while (!stateManager.isAllFinished()) {
      round++;

      const window = createCenteredWindow(stateManager, this.config.windowSize);
      if (!window) break;

      logger.info(`Round ${round}:`);
      logger.info(formatWindowDisplay(window));
      logger.separator();

      // Simulate marking all as finished for next window
      for (const entry of window.entries) {
        if (entry.state === 'unfinished') {
          stateManager.markFine(entry.index);
        }
      }
    }

    logger.info(`\nTotal rounds (simulated): ${round}`);
    logger.info('Run without --dry-run to perform actual refinement');

    return stateManager.export();
  }

  /**
   * Print final summary
   */
  private printSummary(): void {
    logger.header('Refinement Complete');
    logger.success(`Total rounds: ${this.stats.rounds}`);
    logger.success(`LLM API calls: ${this.stats.llmCalls}`);
    logger.success(`Finished subtitles: ${this.stats.finishedSubtitles}/${this.stats.totalSubtitles}`);
    logger.success(`Refined subtitles: ${this.stats.refinedSubtitles}`);

    if (this.stats.refinedSubtitles > 0) {
      const percentage = ((this.stats.refinedSubtitles / this.stats.totalSubtitles) * 100).toFixed(1);
      logger.info(`Refinement rate: ${percentage}%`);
    }
  }

  /**
   * Sleep utility
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}
