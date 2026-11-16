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
