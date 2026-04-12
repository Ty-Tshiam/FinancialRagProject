import re

def resolve_footnotes(content):
    # 1. Find all footnotes at the bottom of the content
    # Look for lines like "1 Some text" or "2 More text" at the end of the content
    # We assume footnotes are at the end of the page/content
    lines = content.split('\n')
    footnote_defs = {}
    remaining_lines = []
    
    # Simple heuristic: footnotes usually appear at the end and start with a number + space
    # and they often follow a pattern of 1, 2, 3...
    for line in lines:
        match = re.match(r'^(\d+)\s+(.*)', line.strip())
        if match:
            num = match.group(1)
            text = match.group(2)
            footnote_defs[num] = text
        else:
            remaining_lines.append(line)

    if not footnote_defs:
        return content

    new_content = "\n".join(remaining_lines)
    
    # 2. Replace markers in the text. 
    # Markers are often "word1" or "word2" where the number is a superscript or just a trailing digit.
    # This regex looks for digits that are NOT part of a larger number (like 2025) 
    # and match our extracted footnote IDs.
    for num, text in footnote_defs.items():
        # Replace occurrences of the number when it's used as a marker
        # We look for: 
        # (a) A word followed immediately by the digit, but NOT another digit
        # (b) Or the digit in a table cell alone or with (Note X)
        
        # Pattern for word1: (letter)(digit)(not-digit)
        # Using a lambda to ensure we don't accidentally replace years like 2025
        pattern = rf'([a-zA-Z])({num})(\b|[^\d])'
        replacement = rf'\1 [Footnote {num}: {text}]\3'
        new_content = re.sub(pattern, replacement, new_content)
        
        # Pattern for table cells: <td>1</td> or <td>(Note 1)</td>
        new_content = new_content.replace(f'<td>{num}</td>', f'<td>[Footnote {num}: {text}]</td>')
        new_content = new_content.replace(f'(Note {num})', f'(Note {num}: {text})')

    return new_content

# Test
test_content = """
The bank grew its loan volume1 this year.
In addition, net income increased significantly (Note 2).

1 Loan volume includes personal and commercial.
2 Based on adjusted net income.
"""

print("BEFORE:")
print(test_content)
print("\nAFTER:")
print(resolve_footnotes(test_content))
