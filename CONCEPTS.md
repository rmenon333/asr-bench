# CONCEPTS.md — plain-English revision sheet

The ideas behind this project, each with an everyday analogy. One section is added per build step.
For *what the code does*, see `LEARNING.md`. This file is for *the ideas*.

---

## 1. Speech-to-text (ASR) and Whisper
**ASR (automatic speech recognition)** turns spoken audio into written text. **Whisper** is a family of ASR models from OpenAI that come in sizes, from `tiny` to `large`. Bigger models are usually more accurate, but slower and more expensive to run.
- **Analogy:** a small car vs a lorry. The lorry carries more, but costs more fuel and is slower through town. We are measuring how much "cargo" (accuracy) each size really delivers on bumpy roads (noisy phone audio).

## 2. Reference text
The **reference** is the correct transcript: what was actually said, written down by a person. We compare the model's output (the **hypothesis**) against it.
- **Analogy:** the answer key for a test.

## 3. Seeded random sample
We test a random subset of sentences. A fixed **seed** makes the "random" choice repeatable.
- **Analogy:** shuffling a deck in exactly the same way every time. It's fair because nobody hand-picked the cards, and it's repeatable because anyone can deal the same hand.
- Our sample of 5 is always the first 5 of the sample of 20, so a quick test and the full run share sentences.

---

## 4. Conditions: one recording, different situations
A **condition** is a way of degrading the same clean recording: over a phone line, with background noise, or both. Every model hears every condition.
- **Analogy:** a blind taste test with the *same coffee* served in different cups. If the rating changes, the cup made the difference, not the coffee.

| Condition | What it simulates |
|---|---|
| `clean` | the original studio-quality recording |
| `telephony` | the same voice over a classic phone line |
| `noisy_20db` | quiet office, faint fan |
| `noisy_10db` | busy café |
| `noisy_5db` | talking next to a busy road |
| `telephony_noisy_10db` | a caller in a café, heard over the phone |

## 5. Telephony: a narrow pipe for sound
**Pitch** is measured in **Hz** (vibrations per second). Human hearing spans very deep to very high pitches. A classic phone line only passes the middle: about **300–3,400 Hz**.
- **Analogy:** a song on a cheap pocket radio. No deep bass, no crisp highs, but you can follow the words.
- That's why "s" and "f" are hard to tell apart on the phone: the difference lives in the high pitches that get cut.

## 6. Sample rate
Digital audio is a series of snapshots of the sound wave. **Sample rate** is how many snapshots per second: 16,000 (16 kHz) for our models, 8,000 (8 kHz) for a phone line.
- **Analogy:** a flipbook. Fewer pages per second means less detail.
- Converting phone audio back up to 16 kHz does **not** bring the detail back, just as photocopying a blurry photo at higher resolution doesn't sharpen it.

## 7. Noise, SNR and decibels (dB)
**SNR (signal-to-noise ratio)** answers: *how much louder is the voice than the background?* It's measured in **decibels (dB)**. A higher number means the voice stands out more.
- Every **+10 dB** means the voice has **10×** the power of the noise. So 20 dB = 100×, 10 dB = 10×, 5 dB ≈ 3×.
- **How we measure voice loudness:** the average over the whole clip, including short pauses. It's simple and standard. The side effect is that clips with many pauses get slightly harsher noise *during* the words.

## 8. White vs pink noise
- **White noise:** equal energy at every pitch. It sounds like the "ssshhh" of an untuned TV.
- **Pink noise:** the higher pitches are turned down, so each octave (each doubling of pitch) gets equal energy. It sounds deeper, like steady rain or an air-conditioner, and is closer to real background noise. **We use pink.**

## 9. Room noise goes through the phone too
On a real call, the background noise (TV, traffic, kids) is **in the caller's room**. It enters the phone *with* the voice, and the phone line squeezes both.
- The phone line cuts much of pink noise's deep rumble. Left alone, "10 dB" would really have been an easier 12–15 dB at the agent's end.
- **What we do:** set the room noise loud enough that what reaches the agent is **exactly 10 dB**. The label stays honest and is comparable with plain `noisy_10db`.
- **Analogy:** setting a café's background music so that it's at a given level *as heard by the person on the other end of the call*, not as heard in the café.

## 10. Fairness: the same noise for every model
For each sentence, every model hears **identical** noise, down to the last crackle. The noise is "seeded" from the sentence's ID.
- **Analogy:** every runner in a race faces the same headwind. Otherwise you can't separate skill from luck.

## 11. Verifying with tests
We don't just trust the code. Automated **tests** check, for example, that "10 dB" really measures 10 dB (within 0.5 dB) and that the phone line really removes very low and very high pitches.
- **Analogy:** calibrating a weighing scale with a known 1 kg weight before weighing anything else.

---

## 12. WER (word error rate)
WER is how many word fixes a proof-reader would need to turn the model's text into the correct text, divided by the number of words actually spoken. There are three kinds of fix:
- **Substitution:** wrong word ("formerly" instead of "formally").
- **Deletion:** a word the model missed.
- **Insertion:** an extra word the model invented.

**10% WER ≈ 1 wrong word in 10.** Lower is better. WER can go **above 100%** if the model invents lots of words. For example, under heavy noise a model may repeat itself ("6th, 6th, 6th, 6th…").
- **Analogy:** marking a dictation test, where each fix costs one mark.

## 13. Normalisation: what counts as "the same word"
Before marking, both texts are cleaned the same way: lower case, punctuation removed. For English, "twenty five" = "25" and "Dr." = "doctor".
- **Analogy:** a teacher who doesn't take marks off for a missing full stop or for writing "25" instead of "twenty-five", only for genuinely wrong words.
- A stricter or looser teacher gives different scores. That's **hypothesis 4**: the cleaning rules alone might change which model "wins".
- Known gap: for Spanish and German we don't convert numbers, so "2017" vs a spelled-out year counts as an error. Joined vs split words ("checkpoints" vs "check points") also count as errors in every language.

## 14. Overall WER: total mistakes ÷ total words
To score a group of sentences, we add up all mistakes and divide by all words. We do **not** average each sentence's percentage.
- **Analogy:** a student's overall exam mark is total marks earned ÷ total marks available. A 3-question quiz shouldn't count as much as a 30-question paper.

## 15. Latency, warm-up, and p50 / p95
- **Latency:** stopwatch time from handing over a clip to getting the full text back.
- **Warm-up:** the first clip is always slower while the model sets up memory. We run one untimed clip first. **Analogy:** a car on a cold morning.
- **p50 (median):** half the clips were faster than this. It's the "typical" experience.
- **p95:** 95% of clips were faster than this. It's the "bad day" experience, and often matters more to users than the average. **Analogy:** a commute that usually takes 30 minutes (p50) but sometimes 55 (p95). You plan around the 55.

## 16. RTF (real-time factor)
RTF = processing time ÷ audio length.
- **RTF 0.1** means a 10-second clip takes 1 second.
- **Below 1** means the model can keep up with someone talking live. **Above 1** means it falls behind.
- **Analogy:** a typist taking dictation. RTF 0.5 means they type twice as fast as you speak.
