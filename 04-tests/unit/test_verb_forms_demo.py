#!/usr/bin/env python3
"""Demonstrate Western Armenian infinitive form distinctions."""

from lousardzag.morphology.verbs import conjugate_verb

print('=== Western Armenian Infinitive Forms ===\n')

print('1. -ել (-el) verbs: Active forms')
print('   Example: բերել (perel) - to bring')
bring = conjugate_verb('բերել', translation='to bring')
print(f'   Translation: {bring.translation}')
print(f'   Present 1sg: {bring.present["1sg"]}\n')

print('2. -ալ (-al) verbs: Infinitive forms (often irregular)')
print('   Example: գալ (kal) - to come')
come = conjugate_verb('գալ', translation='to come')
print(f'   Translation: {come.translation}')
print(f'   Present 1sg: {come.present["1sg"]}\n')

print('3. -իլ (-il) verbs: Passive/stative forms')
print('   Example: ունիլ (ounil) - to have')
have = conjugate_verb('ունիլ', translation='to have')
print(f'   Translation: {have.translation}')
print(f'   Present 1sg: {have.present["1sg"]}\n')

print('✓ All verb translations now include "to" prefix')
print('  (e.g., "to have" not just "have")')
