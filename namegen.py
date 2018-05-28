"""
This name generator is an improved version of das' random syllable-based
name generator.

Original source at: https://codereview.stackexchange.com/q/156903
Improved by: Gustavo R. Rehermann (Gustavo6046)
"""

import random

vowels = "aeiou"
consonants = "bcdfghjklmnpqrstvwxyz"
pre_consonants = "tspdkcmn"
post_consonants = "rhpzk"
ditongs = ["ae", "ai", "ou", "ao", "oe", "oi", "oy", "aeo", "eio"]

def generate_name(length, digraph_rate=0.3, ditong_rate=0.2, hyphen_rate=0.125):
    if length <= 0:
        return False

    full_syl = ""
    fl = length
    
    while length > 0:
        if full_syl == '':
            decision = random.choice(('consonant', 'vowel'))

        elif full_syl[-1:].lower() in vowels:
            decision = 'consonant'
            
        elif full_syl[-1:].lower() in consonants:
            decision = 'vowel'

        if random.random() <= hyphen_rate and len(full_syl) > 0 and len(full_syl.split('-')[-1]) > 2:
            syl_choice = '-'
            
        elif decision == 'consonant':
            if random.random() <= digraph_rate:
                syl_choice = random.choice(pre_consonants) + random.choice(post_consonants)
                # length -= 1
            
            else:
                syl_choice = random.choice(consonants)
            
        else:
            if random.random() <= ditong_rate:
                syl_choice = random.choice(ditongs)
                # length -= 1
                
            else:
                syl_choice = random.choice(vowels)

        full_syl += syl_choice
        length -= len(syl_choice)
    
    return '-'.join(map(lambda x: x[0].upper() + x[1:], filter(lambda x: len(x) > 0, full_syl.split('-'))))[:fl]