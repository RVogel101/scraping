import sys
sys.path.insert(0, '02-src')
from lousardzag.phonetics import get_pronunciation_guide

test_words = ['ուր', 'ղ', 'ռ', 'պետք', 'մեր']
for word in test_words:
    guide = get_pronunciation_guide(word)
    approx = guide['english_approx'][:30]
    print(f'{word:10} → {approx:30} | Difficulty: {guide["difficulty_score"]}/5')
