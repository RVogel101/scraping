import sys
sys.path.insert(0, '02-src')
from lousardzag.phonetics import get_pronunciation_guide

test_words = ['Õ¸Ö‚Ö€', 'Õ²', 'Õ¼', 'ÕºÕ¥Õ¿Ö„', 'Õ´Õ¥Ö€']
for word in test_words:
    guide = get_pronunciation_guide(word)
    approx = guide['english_approx'][:30]
    print(f'{word:10} â†’ {approx:30} | Difficulty: {guide["difficulty_score"]}/5')

