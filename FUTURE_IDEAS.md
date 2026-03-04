# Future Ideas

- Conversation practice mode: revisit piping responses from a Western Armenian LLM to support guided dialogue practice without adding heavy learner friction.

- **Custom Western Armenian TTS model**: Train a text-to-speech model on Western Armenian speakers to replace Google TTS (which uses Eastern Armenian pronunciation). Best approach: fine-tune **XTTS v2** (Coqui TTS) — needs only ~30 min of clean audio from a native speaker. Steps: (1) collect audio recordings + matching Armenian transcriptions, (2) segment into 5-15 sec clips, (3) fine-tune XTTS v2 or train a Piper voice, (4) integrate into card generation pipelines (`generate_letter_audio`, `generate_vocab_audio`). Key challenge is data collection — no existing WA TTS models exist. The project's `phonetics.py` Western Armenian phoneme set would inform the phoneme mapping. Potential audio sources: record a native speaker reading the vocabulary list, diaspora radio/TV archives, or clean existing Anki audio files.
