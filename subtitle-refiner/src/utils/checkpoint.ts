/**
 * Checkpoint system for saving and resuming refinement progress
 */

import fs from 'fs';
import path from 'path';
import { Subtitle, SubtitleWithState, LanguageInfo } from '../types.js';
import { logger } from './logger.js';

export interface CheckpointData {
  version: string;
  inputFile: string;
  timestamp: number;
  languageInfo: LanguageInfo | null;
  progress: {
    totalSubtitles: number;
    finishedSubtitles: number;
    refinedSubtitles: number;
    rounds: number;
    llmCalls: number;
  };
  subtitles: SubtitleWithState[];
  windowStartPosition: number | null;
}

/**
 * Get checkpoint file path for an input file
 */
export function getCheckpointPath(inputFile: string): string {
  const dir = path.dirname(inputFile);
  const basename = path.basename(inputFile, path.extname(inputFile));
  return path.join(dir, `${basename}.checkpoint.json`);
}

/**
 * Check if a checkpoint exists
 */
export function checkpointExists(inputFile: string): boolean {
  const checkpointPath = getCheckpointPath(inputFile);
  return fs.existsSync(checkpointPath);
}

/**
 * Save checkpoint to disk
 */
export function saveCheckpoint(
  inputFile: string,
  languageInfo: LanguageInfo | null,
  subtitles: SubtitleWithState[],
  progress: CheckpointData['progress'],
  windowStartPosition: number | null = null
): void {
  const checkpointPath = getCheckpointPath(inputFile);

  const data: CheckpointData = {
    version: '1.0.0',
    inputFile,
    timestamp: Date.now(),
    languageInfo,
    progress,
    subtitles,
    windowStartPosition,
  };

  try {
    fs.writeFileSync(checkpointPath, JSON.stringify(data, null, 2), 'utf-8');
    logger.debug(`Checkpoint saved: ${checkpointPath}`);
  } catch (error) {
    logger.warn(`Failed to save checkpoint: ${error}`);
  }
}

/**
 * Load checkpoint from disk
 */
export function loadCheckpoint(inputFile: string): CheckpointData | null {
  const checkpointPath = getCheckpointPath(inputFile);

  if (!fs.existsSync(checkpointPath)) {
    return null;
  }

  try {
    const content = fs.readFileSync(checkpointPath, 'utf-8');
    const data = JSON.parse(content) as CheckpointData;

    // Validate checkpoint
    if (data.version !== '1.0.0') {
      logger.warn('Checkpoint version mismatch, ignoring');
      return null;
    }

    if (data.inputFile !== inputFile) {
      logger.warn('Checkpoint input file mismatch, ignoring');
      return null;
    }

    logger.success(`Loaded checkpoint from ${new Date(data.timestamp).toLocaleString()}`);
    logger.info(
      `Progress: ${data.progress.finishedSubtitles}/${data.progress.totalSubtitles} finished, ` +
        `${data.progress.rounds} rounds, ${data.progress.llmCalls} LLM calls`
    );

    return data;
  } catch (error) {
    logger.warn(`Failed to load checkpoint: ${error}`);
    return null;
  }
}

/**
 * Delete checkpoint file
 */
export function deleteCheckpoint(inputFile: string): void {
  const checkpointPath = getCheckpointPath(inputFile);

  if (fs.existsSync(checkpointPath)) {
    try {
      fs.unlinkSync(checkpointPath);
      logger.debug(`Checkpoint deleted: ${checkpointPath}`);
    } catch (error) {
      logger.warn(`Failed to delete checkpoint: ${error}`);
    }
  }
}

/**
 * Get human-readable checkpoint info
 */
export function getCheckpointInfo(inputFile: string): string | null {
  const checkpoint = loadCheckpoint(inputFile);
  if (!checkpoint) {
    return null;
  }

  const date = new Date(checkpoint.timestamp).toLocaleString();
  const progress = checkpoint.progress;
  const percentage = ((progress.finishedSubtitles / progress.totalSubtitles) * 100).toFixed(1);

  return `Checkpoint from ${date}\n` +
    `Progress: ${progress.finishedSubtitles}/${progress.totalSubtitles} (${percentage}%)\n` +
    `Rounds: ${progress.rounds}, LLM calls: ${progress.llmCalls}`;
}
