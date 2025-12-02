#!/usr/bin/env python3
"""
Fix pronunciation issues in refined subtitle file

Keep homophone/single-character substitutions (住→著, 题→体)
Restore significant changes that affect pronunciation
"""

import re
from difflib import SequenceMatcher


def parse_srt(filepath):
    """Parse SRT file and return list of entries"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # Match SRT entries
    pattern = r'(\d+)\n([\d:,]+ --> [\d:,]+)\n(.*?)\n(.*?)\n(?:\n|$)'
    matches = re.findall(pattern, content, re.MULTILINE | re.DOTALL)

    entries = []
    for num, time, line1, line2 in matches:
        entries.append({
            'index': int(num),
            'time': time,
            'eng': line1.strip(),
            'cmn': line2.strip()
        })
    return entries


def extract_chinese_chars(text):
    """Extract only Chinese characters from text"""
    return ''.join([c for c in text if '\u4e00' <= c <= '\u9fff'])


def should_restore(original, refined):
    """
    Determine if we should restore original text

    Rules:
    - Keep if only punctuation changed
    - Keep if single character substitution (likely homophone: 住→著)
    - Keep if only added/removed particles (的、了、吗、吧)
    - Restore if words added/removed/changed significantly
    """
    orig_chars = extract_chinese_chars(original)
    ref_chars = extract_chinese_chars(refined)

    # If no Chinese characters changed, keep refined (punctuation fix)
    if orig_chars == ref_chars:
        print(f"  [Punctuation] {original[:40]}")
        return False

    # Character-level diff
    s = SequenceMatcher(None, orig_chars, ref_chars)

    # Count changes
    replacements = 0
    insertions = 0
    deletions = 0

    for tag, i1, i2, j1, j2 in s.get_opcodes():
        if tag == 'replace':
            # Check if single character substitution
            if (i2 - i1) == 1 and (j2 - j1) == 1:
                # Single char substitution - likely homophone
                replacements += 1
            else:
                # Multi-char replacement - restore
                print(f"  [RESTORE-Multi] {original[:40]}")
                print(f"    Changed: '{orig_chars[i1:i2]}' → '{ref_chars[j1:j2]}'")
                return True
        elif tag == 'insert':
            inserted = ref_chars[j1:j2]
            # Allow common particles
            if inserted in ['的', '了', '吗', '吧', '呢', '啊', '呀', '吧', '呢']:
                insertions += 1
            else:
                print(f"  [RESTORE-Insert] {original[:40]}")
                print(f"    Inserted: '{inserted}'")
                return True
        elif tag == 'delete':
            deleted = orig_chars[i1:i2]
            # Allow removing obvious errors (English remnants)
            if all(ord(c) < 128 or c in '。，' for c in deleted):
                deletions += 1
            else:
                print(f"  [RESTORE-Delete] {original[:40]}")
                print(f"    Deleted: '{deleted}'")
                return True

    # If only single-char substitutions and minor particles, keep refined
    if replacements <= 3 and insertions <= 2 and deletions <= 2:
        print(f"  [Homophone-OK] {original[:40]} (rep={replacements}, ins={insertions}, del={deletions})")
        return False

    print(f"  [RESTORE-TooMany] {original[:40]} (rep={replacements}, ins={insertions}, del={deletions})")
    return True


def fix_pronunciation(original_file, refined_file, output_file):
    """Fix pronunciation issues in refined subtitle"""

    print("="*80)
    print("Fixing Pronunciation Issues in Refined Subtitles")
    print("="*80)
    print()

    # Parse both files
    print("Reading files...")
    original = parse_srt(original_file)
    refined = parse_srt(refined_file)

    print(f"Original entries: {len(original)}")
    print(f"Refined entries: {len(refined)}")
    print()

    # Process entries
    fixed = []
    restored_count = 0
    kept_count = 0
    unchanged_count = 0

    print("Processing entries...")
    print()

    for orig, ref in zip(original, refined):
        if orig['cmn'] != ref['cmn']:
            if should_restore(orig['cmn'], ref['cmn']):
                # Restore original Chinese text
                fixed.append({
                    'index': ref['index'],
                    'time': ref['time'],
                    'eng': ref['eng'],  # Keep refined English
                    'cmn': orig['cmn']  # Restore original Chinese
                })
                restored_count += 1
            else:
                # Keep refined
                fixed.append(ref)
                kept_count += 1
        else:
            # No change
            fixed.append(ref)
            unchanged_count += 1

    print()
    print("="*80)
    print("Statistics")
    print("="*80)
    print(f"Total entries: {len(fixed)}")
    print(f"Unchanged: {unchanged_count} ({unchanged_count/len(fixed)*100:.1f}%)")
    print(f"Kept (homophone/punctuation): {kept_count} ({kept_count/len(fixed)*100:.1f}%)")
    print(f"Restored (pronunciation affected): {restored_count} ({restored_count/len(fixed)*100:.1f}%)")
    print()

    # Write output file
    print(f"Writing to {output_file}...")
    with open(output_file, 'w', encoding='utf-8') as f:
        for entry in fixed:
            f.write(f"{entry['index']}\n")
            f.write(f"{entry['time']}\n")
            f.write(f"{entry['eng']}\n")
            f.write(f"{entry['cmn']}\n")
            f.write("\n")

    print("✓ Done!")
    print()


if __name__ == "__main__":
    original_file = "assets/066. 移民第五季 第十三集.cmn-eng.srt"
    refined_file = "assets/066. 移民第五季 第十三集.cmn-eng.refined.srt"
    output_file = "assets/066. 移民第五季 第十三集.cmn-eng.refined.fixed.srt"

    fix_pronunciation(original_file, refined_file, output_file)
