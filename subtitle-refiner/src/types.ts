/**
 * Subtitle entry structure
 */
export interface Subtitle {
  index: number;
  start: number; // seconds
  end: number; // seconds
  text: string; // raw text (may contain newlines for bilingual)
  lines?: string[]; // split lines for bilingual subtitles
}

/**
 * Subtitle processing state
 */
export type SubtitleState = 'unfinished' | 'finished';

/**
 * Subtitle with state tracking
 */
export interface SubtitleWithState extends Subtitle {
  state: SubtitleState;
  refined?: {
    srcText: string;
    tarText: string;
  };
}

/**
 * Sliding window of subtitles with center-first-unfinished strategy
 */
export interface SubtitleWindow {
  entries: SubtitleWithState[];
  firstUnfinishedIndex: number; // Global index of first unfinished subtitle
  windowStartIndex: number; // Global index of window start
  windowEndIndex: number; // Global index of window end
  contextCount: number; // Number of finished entries before first unfinished
  unfinishedCount: number; // Number of unfinished entries in window
}

/**
 * Function call result from LLM
 */
export interface FunctionCall {
  name: 'this_is_fine' | 'this_should_be';
  arguments: {
    id?: number;
    src_text?: string;
    tar_text?: string;
  };
}

/**
 * LLM provider interface with function calling support
 */
export interface LLMProvider {
  refine(
    window: SubtitleWindow,
    systemPrompt: string,
    retryPrompt?: string
  ): Promise<FunctionCall[]>;
  getName(): string;
  supportsFunctionCalling(): boolean;
}

/**
 * Configuration options
 */
export interface RefinerConfig {
  provider: string;
  model?: string;
  windowSize: number;
  dryRun: boolean;
  verbose: boolean;
  maxRetries: number;
}

/**
 * Processing statistics
 */
export interface ProcessingStats {
  totalSubtitles: number;
  finishedSubtitles: number;
  refinedSubtitles: number;
  rounds: number;
  noProgressRounds: number;
  llmCalls: number;
}
