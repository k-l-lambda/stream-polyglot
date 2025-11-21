import { Subtitle, SubtitleWithState, SubtitleState } from '../types.js';

/**
 * Manages subtitle processing state
 */
export class SubtitleStateManager {
  private subtitles: SubtitleWithState[];

  constructor(subtitles: Subtitle[]) {
    // Initialize all subtitles as unfinished
    this.subtitles = subtitles.map((sub) => ({
      ...sub,
      state: 'unfinished' as SubtitleState,
    }));
  }

  /**
   * Get all subtitles with state
   */
  getAll(): SubtitleWithState[] {
    return this.subtitles;
  }

  /**
   * Get subtitle by index (1-based)
   */
  get(index: number): SubtitleWithState | undefined {
    return this.subtitles[index - 1];
  }

  /**
   * Mark subtitle as finished without changes
   */
  markFine(index: number): boolean {
    const sub = this.get(index);
    if (!sub) return false;

    sub.state = 'finished';
    return true;
  }

  /**
   * Mark subtitle as finished with refined text
   */
  markRefined(index: number, srcText: string, tarText: string): boolean {
    const sub = this.get(index);
    if (!sub) return false;

    sub.state = 'finished';
    sub.refined = { srcText, tarText };
    sub.text = `${tarText}\n${srcText}`;
    sub.lines = [tarText, srcText];
    return true;
  }

  /**
   * Find index of first unfinished subtitle (1-based index)
   * Returns -1 if all finished
   */
  findFirstUnfinished(): number {
    const index = this.subtitles.findIndex((sub) => sub.state === 'unfinished');
    return index === -1 ? -1 : index + 1;
  }

  /**
   * Get finished count
   */
  getFinishedCount(): number {
    return this.subtitles.filter((sub) => sub.state === 'finished').length;
  }

  /**
   * Get refined count (finished with changes)
   */
  getRefinedCount(): number {
    return this.subtitles.filter((sub) => sub.refined).length;
  }

  /**
   * Check if all subtitles are finished
   */
  isAllFinished(): boolean {
    return this.findFirstUnfinished() === -1;
  }

  /**
   * Get subtitles in range (1-based, inclusive)
   */
  getRange(start: number, end: number): SubtitleWithState[] {
    const startIdx = Math.max(0, start - 1);
    const endIdx = Math.min(this.subtitles.length, end);
    return this.subtitles.slice(startIdx, endIdx);
  }

  /**
   * Get total count
   */
  getTotalCount(): number {
    return this.subtitles.length;
  }

  /**
   * Export to plain Subtitle array (with refined text applied)
   */
  export(): Subtitle[] {
    return this.subtitles.map((sub) => ({
      index: sub.index,
      start: sub.start,
      end: sub.end,
      text: sub.text,
      lines: sub.lines,
    }));
  }
}
