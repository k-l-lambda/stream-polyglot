import { LLMProvider, RefinerConfig, ProcessingStats, Subtitle, LanguageInfo } from '../types.js';
import { SubtitleStateManager } from '../utils/state-manager.js';
import { createCenteredWindow, formatWindowDisplay } from '../utils/window.js';
import { logger } from '../utils/logger.js';
import { buildSystemPrompt } from '../prompts/default-prompts.js';
import {
  saveCheckpoint,
  loadCheckpoint,
  deleteCheckpoint,
  checkpointExists,
} from '../utils/checkpoint.js';

export class SubtitleRefiner {
  private provider: LLMProvider;
  private config: RefinerConfig;
  private stats: ProcessingStats;

  constructor(provider: LLMProvider, config: RefinerConfig) {
    this.provider = provider;
    this.config = config;
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
  async refine(
    subtitles: Subtitle[],
    languageInfo: LanguageInfo | null = null,
    inputFile: string = ''
  ): Promise<Subtitle[]> {
    if (subtitles.length === 0) {
      logger.warn('No subtitles to refine');
      return subtitles;
    }

    logger.header('Subtitle Refiner with Function Calling');
    logger.info(`Provider: ${this.provider.getName()}`);
    logger.info(`Window size: ${this.config.windowSize}`);
    logger.info(`Total subtitles: ${subtitles.length}`);

    // Check for checkpoint if resume is enabled
    let stateManager: SubtitleStateManager;
    let startRound = 0;
    let windowStartPosition: number | null = null;

    if (this.config.resume && inputFile && checkpointExists(inputFile)) {
      const checkpoint = loadCheckpoint(inputFile);

      if (checkpoint) {
        logger.info('Resuming from checkpoint...');
        logger.separator();

        // Restore state from checkpoint
        stateManager = new SubtitleStateManager(checkpoint.subtitles, checkpoint.languageInfo);
        // Restore stats, setting noProgressRounds to 0 (start fresh on resume)
        this.stats = {
          ...checkpoint.progress,
          noProgressRounds: 0,
        };
        startRound = checkpoint.progress.rounds;
        // Don't restore windowStartPosition - let it recalculate naturally
        // based on current firstUnfinished position
        windowStartPosition = null;

        logger.info(`Resumed at round ${startRound + 1}`);
        logger.info(
          `Progress: ${this.stats.finishedSubtitles}/${this.stats.totalSubtitles} finished`
        );
      } else {
        // Checkpoint load failed, start fresh
        stateManager = new SubtitleStateManager(subtitles, languageInfo);
        this.stats.totalSubtitles = subtitles.length;
      }
    } else {
      // No checkpoint or resume disabled, start fresh
      stateManager = new SubtitleStateManager(subtitles, languageInfo);
      this.stats.totalSubtitles = subtitles.length;
    }

    logger.separator();

    if (this.config.dryRun) {
      return this.dryRun(stateManager);
    }

    // Build system prompt with language info
    const systemPrompt = buildSystemPrompt(languageInfo);

    // Main processing loop
    let round = startRound;
    let previousFirstUnfinished = -1;

    while (!stateManager.isAllFinished()) {
      round++;
      this.stats.rounds = round;

      // Create window with optional preferred start position
      const window = createCenteredWindow(
        stateManager,
        this.config.windowSize,
        windowStartPosition
      );

      if (!window) {
        break; // All finished
      }

      // Log if window position was adjusted by constraints
      if (windowStartPosition !== null && window.windowStartIndex !== windowStartPosition) {
        const extraSteps = window.windowStartIndex - windowStartPosition;
        logger.info(
          `(Window adjusted by constraint: intended #${windowStartPosition} → actual #${window.windowStartIndex}, moved ${extraSteps} extra step${extraSteps > 1 ? 's' : ''})`
        );
      }

      logger.header(`Round ${round}`);
      logger.info(formatWindowDisplay(window));
      logger.separator();

      try {
        this.stats.llmCalls++;
        const functionCalls = await this.provider.refine(
          window,
          systemPrompt,
          false // First attempt is never a retry
        );

        // Process function calls
        let processedCount = 0;

        for (const call of functionCalls) {
          const success = this.processFunctionCall(stateManager, call);
          if (success) processedCount++;
        }

        logger.success(`Processed ${processedCount} function calls`);

        // Check if stuck (no actual progress from last round)
        const noProgress = window.firstUnfinishedIndex === previousFirstUnfinished;
        const firstEntryFinished = window.entries.length > 0 && window.entries[0].state === 'finished';
        const hasFunctionCalls = functionCalls.length > 0;

        logger.debug(`Progress check: noProgress=${noProgress}, firstEntryFinished=${firstEntryFinished}, hasFunctionCalls=${hasFunctionCalls}`);
        logger.debug(`Window state: firstUnfinished=#${window.firstUnfinishedIndex}, previousFirstUnfinished=#${previousFirstUnfinished}, windowStartPosition=${windowStartPosition}`);

        // If window didn't move and first entry is already finished, force window to slide forward
        if (noProgress && firstEntryFinished) {
          logger.info(`Window didn't move and first entry #${window.entries[0].index} is already finished`);

          // Move window start position forward by 1 (may move more due to constraints)
          const oldStart: number = window.windowStartIndex;
          windowStartPosition = oldStart + 1;

          logger.info(`Forcing window to slide forward (next start: #${windowStartPosition})`);
          this.stats.noProgressRounds = 0;
        } else if (noProgress && !hasFunctionCalls) {
          // Truly stuck: LLM didn't call any functions and window first entry is not finished
          this.stats.noProgressRounds++;
          logger.warn(`No progress detected: still at #${window.firstUnfinishedIndex}, no function calls`);

          // Fail if stuck too long
          if (this.stats.noProgressRounds >= this.config.maxRetries) {
            logger.error(`Failed after ${this.config.maxRetries} attempts with no progress`);
            logger.error('LLM is not calling functions properly');
            throw new Error(
              `Refinement failed: No progress after ${this.config.maxRetries} rounds`
            );
          }

          // Retry with same window and RETRY_PROMPT
          logger.info('Retrying with RETRY_PROMPT...');
          this.stats.llmCalls++;
          const retryFunctionCalls = await this.provider.refine(
            window,
            systemPrompt,
            true // Retry mode
          );

          // Process retry function calls
          let retryProcessedCount = 0;
          for (const call of retryFunctionCalls) {
            const success = this.processFunctionCall(stateManager, call);
            if (success) retryProcessedCount++;
          }

          logger.success(`Retry processed ${retryProcessedCount} function calls`);
        } else {
          // Normal case - could be progress or no progress with function calls
          // Only reset forced window position if actual progress was made
          if (!noProgress) {
            // firstUnfinished moved forward - return to centered window
            logger.debug(`Progress made! Resetting windowStartPosition from ${windowStartPosition} to null`);
            windowStartPosition = null;
          } else {
            // If noProgress but we're here, it means LLM called functions but they were duplicates
            // Keep windowStartPosition as-is for next iteration
            logger.debug(`No progress but functions called. Keeping windowStartPosition=${windowStartPosition}`);
          }
          this.stats.noProgressRounds = 0;
        }

        // Update stats
        this.stats.finishedSubtitles = stateManager.getFinishedCount();
        this.stats.refinedSubtitles = stateManager.getRefinedCount();

        logger.info(
          `Progress: ${this.stats.finishedSubtitles}/${this.stats.totalSubtitles} finished`
        );
        logger.separator();

        // Update previous position with current state (after all processing)
        previousFirstUnfinished = stateManager.findFirstUnfinished();

        // Save checkpoint if enabled and at interval
        if (
          this.config.checkpointInterval > 0 &&
          inputFile &&
          round % this.config.checkpointInterval === 0
        ) {
          saveCheckpoint(
            inputFile,
            languageInfo,
            stateManager.getAllWithState(),
            this.stats,
            windowStartPosition
          );
          logger.info(`Checkpoint saved (round ${round})`);
        }

        // Brief delay to avoid rate limits
        await this.sleep(500);
      } catch (error) {
        logger.error(`Error in round ${round}`);
        if (error instanceof Error) {
          logger.error(error.message);
        }
        // Save checkpoint on error
        if (this.config.checkpointInterval > 0 && inputFile) {
          saveCheckpoint(
            inputFile,
            languageInfo,
            stateManager.getAllWithState(),
            this.stats,
            windowStartPosition
          );
          logger.info('Checkpoint saved before exit');
        }
        throw error;
      }
    }

    // Final summary
    this.printSummary();

    // Delete checkpoint on successful completion
    if (inputFile) {
      deleteCheckpoint(inputFile);
      logger.debug('Checkpoint cleaned up');
    }

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
        const sub = stateManager.get(id);
        if (!sub) {
          logger.warn(`Failed to mark #${id} (not found)`);
        } else if (sub.state === 'finished') {
          logger.debug(`⊚ #${id} already finished (duplicate call)`);
        }
      }
      return success;
    } else if (call.name === 'this_should_be') {
      const firstLangText = call.arguments?.first_lang_text;
      const secondLangText = call.arguments?.second_lang_text;

      if (!firstLangText || !secondLangText) {
        logger.warn(`Invalid this_should_be call for #${id}: missing text`);
        return false;
      }

      const success = stateManager.markRefined(id, firstLangText, secondLangText);
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
