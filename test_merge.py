#!/usr/bin/env python3

import pandas as pd
import re

def should_merge_up(text, word_tolerance=15):
    if not text or text == 'nan':
        return False
    
    text = text.strip()
    word_count = len(text.split())
    
    # Check if it's a short, lowercase description
    if word_count < word_tolerance and not text.isupper():
        # Check if it doesn't start with a capital letter (indicating it's not a section header)
        if text and not text[0].isupper():
            return True
        # Also check if it's all lowercase (common for continuation text)
        if text.islower():
            return True
    
    return False

def is_section_header(text, word_tolerance=15):
    if not text or text == 'nan':
        return False
    
    text = text.strip()
    
    # Check for colon ending (common in section headers)
    if text.endswith(':'):
        return True
    
    # Check if it's a short, standalone phrase
    word_count = len(text.split())
    if word_count < word_tolerance:
        # Check if it doesn't end with continuation words
        continuation_words = ['and', 'or', 'the', 'of', 'in', 'to', 'for', 'with', 'by', 'from']
        words = text.lower().split()
        if words and words[-1] not in continuation_words:
            # Check if it looks like a complete phrase
            if not text.endswith(',') and not text.endswith(';'):
                return True
    
    # Check for specific patterns that indicate section headers
    header_patterns = [
        r'^[A-Z][a-z\s]+:$',  # Capitalized words ending with colon
        r'^[A-Z\s]+$',        # All caps (like "ASSETS")
        r'^[A-Z][a-z\s]+assets?$',  # Ends with "asset" or "assets"
        r'^[A-Z][a-z\s]+liabilities?$',  # Ends with "liability" or "liabilities"
        r'^[A-Z][a-z\s]+equity$',  # Ends with "equity"
    ]
    
    for pattern in header_patterns:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    
    return False

# Test data
test_data = [
    ["Preferred stock, $0.001 par value per share, 100 shares authorized; no shares issued and outstanding", "0", "0"],
    ["Class A, Class B, and Class C stock and additional paid-in capital, $0.001 par value per share: 300,000 shares authorized (Class A 180,000, Class B", "", ""],
    ["60,000, Class C 60,000); 12,211 (Class A 5,835, Class B 861, Class C 5,515) and 12,155 (Class A 5,825, Class B 856, Class C 5,474) shares issued and", "84,800", "86,725"],
    ["outstanding", "", ""],
    ["Accumulated other comprehensive income (loss)", "(4,800)", "(4,086)"]
]

df = pd.DataFrame(test_data, columns=['Description', 'Value1', 'Value2'])

print("Original DataFrame:")
print(df)
print("\n" + "="*80 + "\n")

# Test each row
for i, row in df.iterrows():
    text = str(row['Description']).strip()
    word_count = len(text.split())
    
    # Check if row has numbers
    has_numbers = False
    for col in ['Value1', 'Value2']:
        val = str(row[col]).strip()
        if val and val != 'nan':
            if val.startswith('(') and val.endswith(')') and len(val) > 2:
                bracket_content = val[1:-1]
                if re.match(r'^[\d,]+$', bracket_content):
                    has_numbers = True
                    break
            elif re.match(r'^-?[\d,]+\.?[\d]*$', val.replace(',', '').replace('$', '')):
                has_numbers = True
                break
    
    print(f"Row {i}: '{text}'")
    print(f"  Word count: {word_count}")
    print(f"  Has numbers: {has_numbers}")
    print(f"  Is section header: {is_section_header(text)}")
    print(f"  Should merge up: {should_merge_up(text)}")
    print(f"  Should merge down: {not has_numbers and not is_section_header(text) and word_count >= 15}")
    print() 