import { SubtitleWindow, SubtitleWithState } from '../types.js';
import { SubtitleStateManager } from './state-manager.js';

/**
 * Create window with center-first-unfinished strategy
 *
 * Strategy:
 * - Place first unfinished subtitle at window center
 * - Fill window with context (finished) before it
 * - Fill window with remaining (unfinished) after it
 * - If preferredStart is provided, use it but ensure it's >= firstUnfinished - halfWindow
 *
 * @param stateManager Subtitle state manager
 * @param windowSize Total window size
 * @param preferredStart Optional preferred window start position (independent control)
 * @returns Window or null if all finished
 */
export function createCenteredWindow(
  stateManager: SubtitleStateManager,
  windowSize: number,
  preferredStart: number | null = null
): SubtitleWindow | null {
  const firstUnfinished = stateManager.findFirstUnfinished();

  if (firstUnfinished === -1) {
    return null; // All finished
  }

  const totalCount = stateManager.getTotalCount();
  const halfWindow = Math.floor(windowSize / 2);

  // Calculate default window bounds (centered on first unfinished)
  const defaultStart = firstUnfinished - halfWindow;

  // Use preferredStart if provided, but enforce lower bound
  let windowStart = preferredStart !== null ? preferredStart : defaultStart;

  // Enforce constraint: windowStart >= firstUnfinished - halfWindow
  // This ensures first unfinished is always within the window
  const minStart = firstUnfinished - halfWindow;
  if (windowStart < minStart) {
    windowStart = minStart;
  }

  // Handle boundary: start of file
  if (windowStart < 1) {
    windowStart = 1;
  }

  let windowEnd = windowStart + windowSize - 1;

  // Handle boundary: end of file
  if (windowEnd > totalCount) {
    windowEnd = totalCount;
    windowStart = Math.max(1, totalCount - windowSize + 1);
  }

  // Get entries in window
  const entries = stateManager.getRange(windowStart, windowEnd);

  // Count context (finished before first unfinished)
  let contextCount = 0;
  for (const entry of entries) {
    if (entry.index === firstUnfinished) break;
    if (entry.state === 'finished') contextCount++;
  }

  // Count unfinished in window
  const unfinishedCount = entries.filter((e) => e.state === 'unfinished').length;

  return {
    entries,
    firstUnfinishedIndex: firstUnfinished,
    windowStartIndex: windowStart,
    windowEndIndex: windowEnd,
    contextCount,
    unfinishedCount,
  };
}

/**
 * Format window for display
 */
export function formatWindowDisplay(window: SubtitleWindow): string {
  const lines: string[] = [];

  lines.push(`Window: ${window.windowStartIndex}-${window.windowEndIndex}`);
  lines.push(`First unfinished: #${window.firstUnfinishedIndex} (center)`);
  lines.push(`Context: ${window.contextCount} finished`);
  lines.push(`To process: ${window.unfinishedCount} unfinished`);
  lines.push('');

  for (const entry of window.entries) {
    const marker = entry.state === 'finished' ? '✓' : '○';
    const centerMarker = entry.index === window.firstUnfinishedIndex ? ' ← CENTER' : '';

    // Format preview with proper truncation
    const textLines = entry.text.split('\n');
    let preview: string;

    if (textLines.length === 2) {
      // Bilingual: show both lines with separator, truncate if needed
      const maxLen = 45;
      const line1 = textLines[0].length > maxLen ? textLines[0].substring(0, maxLen) + '...' : textLines[0];
      const line2 = textLines[1].length > maxLen ? textLines[1].substring(0, maxLen) + '...' : textLines[1];
      preview = `${line1} | ${line2}`;
    } else {
      // Monolingual: truncate single line
      const maxLen = 95;
      preview = entry.text.length > maxLen ? entry.text.substring(0, maxLen) + '...' : entry.text;
    }

    lines.push(`  ${marker} [${entry.index}] ${preview}${centerMarker}`);
  }

  return lines.join('\n');
}

/**
 * Format window for LLM (human-readable)
 */
export function formatWindowForLLM(window: SubtitleWindow): string {
  const lines: string[] = [];

  for (const entry of window.entries) {
    const textLines = entry.text.split('\n');

    if (textLines.length === 2) {
      // Bilingual
      lines.push(`Subtitle #${entry.index}:`);
      lines.push(`  Target: ${textLines[0]}`);
      lines.push(`  Source: ${textLines[1]}`);
    } else {
      // Monolingual
      lines.push(`Subtitle #${entry.index}: ${entry.text}`);
    }
    lines.push('');
  }

  return lines.join('\n');
}
