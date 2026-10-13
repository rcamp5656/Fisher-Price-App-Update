"""
audio_processing.py
Contains the real-time audio compressor/limiter logic.
Uses Numba for Just-In-Time (JIT) compilation to optimize the audio processing loop.
"""
import numpy as np
import math
from numba import jit

@jit(nopython=True)
def process_audio_numba(samples_float, envelope, gain, threshold, ratio, makeup_gain, limiter_threshold, alpha_attack, alpha_release):
    """
    High-performance JIT-compiled function for audio processing (compressor/limiter).
    """
    processed_samples = np.zeros_like(samples_float)
    for i, sample in enumerate(samples_float):
        level = abs(sample)
        if level > envelope:
            envelope = alpha_attack * envelope + (1 - alpha_attack) * level
        else:
            envelope = alpha_release * envelope + (1 - alpha_release) * level
        
        envelope_db = 20 * math.log10(envelope) if envelope > 1e-6 else -120.0
        gain_reduction_db = 0.0
        if envelope_db > threshold:
            gain_reduction_db = (threshold - envelope_db) * (1.0 - (1.0 / ratio))
            
        total_gain_db = makeup_gain + gain_reduction_db
        gain = 10 ** (total_gain_db / 20.0)
        compressed_sample = sample * gain
        
        limiter_linear_thresh = 10 ** (limiter_threshold / 20.0)
        if abs(compressed_sample) > limiter_linear_thresh:
            processed_samples[i] = np.sign(compressed_sample) * limiter_linear_thresh
        else:
            processed_samples[i] = compressed_sample
            
    return processed_samples, envelope, gain

class AudioProcessor:
    """
    Holds the state and settings for audio processing, delegating computation
    to the Numba JIT-compiled function.
    """
    def __init__(self, samplerate=44100):
        self.samplerate = float(samplerate)
        self.threshold = -12.0
        self.ratio = 4.0
        self.attack_ms = 5.0
        self.release_ms = 100.0
        self.makeup_gain = 6.0
        self.limiter_threshold = -0.2
        self.envelope = 0.0
        self.gain = 1.0
        self.alpha_attack = math.exp(-1.0 / (self.samplerate * (self.attack_ms / 1000.0)))
        self.alpha_release = math.exp(-1.0 / (self.samplerate * (self.release_ms / 1000.0)))

    def process(self, samples):
        samples_float = samples.astype(np.float32) / 32767.0
        processed_float, new_envelope, new_gain = process_audio_numba(
            samples_float, self.envelope, self.gain, self.threshold, self.ratio,
            self.makeup_gain, self.limiter_threshold, self.alpha_attack, self.alpha_release
        )
        self.envelope = new_envelope
        self.gain = new_gain
        return (processed_float * 32767.0).astype(np.int16)