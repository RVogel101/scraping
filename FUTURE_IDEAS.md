# Future Ideas

- Conversation practice mode: revisit piping responses from a Western Armenian LLM to support guided dialogue practice without adding heavy learner friction.

- **Custom Western Armenian TTS model**: The `facebook/mms-tts-hyw` model (Meta MMS) works well with 3-pass denoising + 0.90x speed, but quality could be improved further. Options: (1) Fine-tune XTTS v2 or train a Piper voice with ~30 min of clean native speaker audio — this would give the highest quality. (2) Explore multi-speaker MMS fine-tuning if Meta releases training code. (3) Use the project's `phonetics.py` Western Armenian phoneme set to inform any phoneme mapping. Current MMS output is usable for flashcards but still has some synthesis artifacts that averaging can't fully remove. Key challenge remains data collection — no existing high-quality WA TTS datasets exist. Potential audio sources: record a native speaker reading the vocabulary list, diaspora radio/TV archives, or clean existing Anki audio files.

- **Letter audio upgrade**: Replace the 76 espeak-ng letter audio files (`08-data/letter_audio/`) with MMS-generated versions using the same 3-pass denoising technique from `generate_vocab_audio_mms.py`. This would give consistent quality across letter and vocabulary audio.

---

## Audio Training Models: Data Requirements & Options

### Text-to-Speech (TTS) Models

#### Training from Scratch
- **Data needed**: 10,000–100,000+ hours of quality speech audio
- **Feasibility**: Not practical for a single project or resource team
- **Use case**: Only for organizations with massive audio budgets (Meta, Google, OpenAI)
- **Relevance**: Not recommended for Lousardzag

#### Fine-tuning Existing TTS Models
**Option 1: Fine-tune XTTS v2 (Multilingual, High Quality)**
- **Data needed**: 20–100 hours of clean Armenian speech
- **Time investment**: 2–4 weeks of preparation + training
- **Quality**: Excellent (comparable to native speaker)
- **Best for**: Custom voice adaptation, character consistency
- **Tool**: Coqui TTS library with XTTS checkpoint
- **Challenges**: Requires GPU (VRAM 8GB+), hyperparameter tuning
- **Pros**: 
  - Already multilingual base (faster convergence)
  - Robust training pipeline
  - High output quality
- **Cons**: 
  - Longer training time
  - More computational overhead

**Option 2: Train a Piper Voice (Lightweight, Fast)**
- **Data needed**: 10–30 hours of consistent native speaker audio
- **Time investment**: 1–2 weeks preparation + training
- **Quality**: Good (clear but slightly less natural than XTTS)
- **Best for**: CPU/GPU-limited environments, fast iteration
- **Tool**: Coqui Piper training scripts
- **Challenges**: Requires strict audio consistency (single speaker, clean recording)
- **Pros**:
  - Smaller model size (~50MB vs XTTS 2GB)
  - Faster inference
  - Easier to retrain
- **Cons**:
  - Less flexible to accent variations
  - Narrower phoneme support

**Option 3: XTTS Fine-tune (Voice Cloning - Minimal Data)**
- **Data needed**: 5–30 minutes of reference audio from target speaker
- **Time investment**: <1 week (mostly data prep)
- **Quality**: Good (speaker-specific, realistic prosody)
- **Best for**: Quick voice adaptation without full retraining
- **Tool**: XTTS speaker embedding API
- **Challenges**: Single speaker only, limited customization
- **Pros**:
  - Extremely fast (<1 hour to adapt)
  - Works with pre-trained base
  - Minimal compute needed
- **Cons**:
  - Less control over output characteristics
  - May inherit artifacts from base model

#### For Armenian Specifically
- **Meta MMS (facebook/mms-tts-hyw)**: Currently working, used in project
  - Strengths: No fine-tuning needed, supports Western Armenian
  - Weakness: Synthesis artifacts, non-native pronunciations
  - Cost to improve: Would need ~20–50 hours to fine-tune XTTS on top of this
- **No existing Western Armenian TTS datasets**: Custom collection required
- **Phoneme validation**: Use `lousardzag/phonetics.py` to ensure all 38 Western Armenian phonemes are properly represented in training targets

---

### Speech Recognition (ASR) Models

#### Training from Scratch
- **Data needed**: 1,000–10,000+ hours of transcribed speech
- **Feasibility**: Not practical without institutional funding
- **Use case**: Foundation models only (Mozilla Common Voice, OpenAI Whisper baseline)

#### Fine-tuning Existing ASR Models
**Option 1: Fine-tune Whisper (Recommended for Armenian)**
- **Data needed**: 50–100 hours of transcribed Armenian speech (word-level accuracy)
- **Time investment**: 2–3 weeks preparation + 1 week training
- **Quality**: Very good (Whisper is robust to accents)
- **Best for**: Learner-facing transcription, accent robustness
- **Tool**: OpenAI Whisper fine-tuning API or Hugging Face Transformers
- **Challenges**:
  - Requires time-aligned transcriptions (WAV file + TXT pairs)
  - Dialect consistency (Western vs. Eastern Armenian must be decided)
- **Pros**:
  - Already multilingual (very fast convergence)
  - Handles acoustic variation well
  - Excellent baseline performance
- **Cons**:
  - Large model (~1.5GB)
  - Slow inference on CPU

**Option 2: Fine-tune Wav2Vec 2.0 (Lightweight)**
- **Data needed**: 100–500 hours for competitive performance
- **Time investment**: 2–4 weeks
- **Quality**: Good (fast, smaller model)
- **Best for**: Real-time applications, mobile deployment
- **Tool**: Hugging Face library
- **Challenges**: Requires extensive data for Armenian-specific phonemes
- **Pros**:
  - Much smaller model (~400MB)
  - Faster inference
  - Lower memory footprint
- **Cons**:
  - Needs more training data to match Whisper quality
  - Less robust to accents out-of-box

---

### Audio Data Collection Strategy for Lousardzag

**For TTS (highest priority):**
1. **Native speaker recording**: Recruit 1–2 fluent Western Armenian speakers
   - Record vocabulary list: 2–3 hours
   - Record example sentences: 5–10 hours
   - Record letter + word examples: 2 hours
   - **Total**: 10–15 hours for basic fine-tuning

2. **Anki deck mining**: Extract existing high-quality audio from Anki deck
   - Estimated: 1–2 hours of curated audio
   - Advantage: Already in training domain

3. **Diaspora media**: Digitize radio/podcast episodes (with speaker consent)
   - Potential: 20–50 hours if sources available

**For ASR (lower priority, optional):**
1. **Collect paired audio + transcripts** from TTS recordings above
2. **Annotate timestamps** using Whisper's automatic alignment
3. **Validation**: Manual QA sampling of 10% of transcribed data

**Storage & Organization:**
```
08-data/audio_training/
├── tts_finetuning/
│   ├── native_speaker_vocab/       # 10-15 hours
│   ├── example_sentences/          # 5-10 hours
│   └── letter_examples/            # 2 hours
├── asr_training/
│   ├── transcribed_segments/       # paired WAV + TXT
│   └── validation_set/             # 10% held-out
└── metadata/
    ├── speaker_info.json           # speaker profiles
    ├── recording_specs.txt         # audio settings (44.1kHz, mono, etc.)
    └── transcription_guidelines.md # consistency rules
```

---

### Recommended Path Forward

**Priority 1 (Immediate)**: Voice cloning with XTTS
- Input: 10–30 minutes of native speaker audio
- Output: Custom Western Armenian TTS in <1 week
- Cost: Minimal (free XTTS library)
- Quality: Good enough for flashcard audio

**Priority 2 (Mid-term)**: XTTS fine-tuning
- Input: 20–50 hours of curated native speaker recordings
- Output: Production-quality TTS voice
- Cost: Moderate (GPU rental ~$200–500 if no local GPU)
- Timeline: 3–6 weeks including data collection

**Priority 3 (Long-term)**: Whisper fine-tuning for ASR
- Input: 50+ hours transcribed speech
- Output: Western Armenian speech recognition
- Use case: Learner pronunciation feedback (not currently in scope)
- Timeline: 2+ months after TTS is stable

---

### Anki Media Audio Audit (March 4, 2026)

**Status**: Inventory completed. Audio useful for evaluation but **insufficient for TTS fine-tuning**.

**Findings**:
- **Total audio**: 2,188 MP3 files + 39 M4A files
- **Size**: ~47 MB MP3 + ~1.3 MB M4A  
- **Estimated duration**: ~75 minutes total
- **Content**: Individual Armenian words (~21.7 KB average per MP3 = ~2 sec/file)
- **M4A subset**: 39 letter name/sound recordings (28–29 KB each)

**Limitation for TTS training**:
- **Need for fine-tuning**: 10–50+ hours of speech minimum
- **Available**: ~1 hour
- **Gap**: 10–50× insufficient
- **Format issue**: Isolated words lack prosody, intonation, sentence-level coarticulation that TTS models learn from connected speech
- **Usefulness**: Validation set only (can evaluate output against existing recordings)

**Recommended action**:
- Use Anki audio as baseline validation/comparison data (placed in `08-data/audio_training/validation_set/`)
- Do NOT use as training data (risk of overfitting to isolated word pronunciation patterns)
- Source native speaker recordings for actual TTS fine-tuning instead
- If repurposing Anki audio: extract, denoise, and segment into phonetic units for analysis only
