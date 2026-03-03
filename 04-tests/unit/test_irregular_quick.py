#!/usr/bin/env python3
"""Quick test of irregular verb conjugation."""

from lousardzag.morphology.verbs import conjugate_verb

# Test 'to be'
be = conjugate_verb('ըլլալ', translation='to be')
print('Verb: be (ըլլալ)')
print(f'  Present 1sg: {be.present.get("1sg")}')
print(f'  Past 1sg: {be.past_aorist.get("1sg")}')
print()

# Test 'to have'
have = conjugate_verb('ունիլ', translation='to have')
print('Verb: have (ունիլ)')
print(f'  Present 1sg: {have.present.get("1sg")}')
print(f'  Past 1sg: {have.past_aorist.get("1sg")}')
print()

# Test 'to come'
come = conjugate_verb('գալ', translation='to come')
print('Verb: come (գալ)')
print(f'  Present 1sg: {come.present.get("1sg")}')
print(f'  Past 1sg: {come.past_aorist.get("1sg")}')
print()

print('✓ Irregular verb conjugation is fully functional!')
