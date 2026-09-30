# Audio Bible

Narration should feel like a person thinking aloud after the fact: calm, conversational and precise. It must not become a speech, a sales pitch, a coach's lecture or a solemn trailer voice.

- Let the selected runtime voice and approved voice ID carry the account identity; this Mode never selects a provider or invents a voice clone.
- Translate the supported delivery choices into the existing Voice Need constraints.voice_delivery (pace_ratio, pitch_semitones, tone), inheriting the frozen mode defaults where no content-specific choice is needed. A description alone is not an executed speech parameter.
- Generate narration before locking shot durations. Use actual audio timings, not character-count estimates, to pace visual beats.
- BGM is optional. When an approved track exists, it should support the emotional movement at a low level and duck under narration. No BGM is better than unlicensed, distracting or fake ambience.
- The frozen music_ducking parameters lower the authored music level during measured speech, with a smooth attack and release. Short breaths remain ducked; longer pauses restore the authored level. This envelope preserves source position and looping. It is not loudness normalization or proof of intelligibility: choose the base music gain against actual audio and verify the finished mix.
- Use SFX only when they belong to a specific visual action. Do not add whooshes, impacts or notification sounds as decoration.
