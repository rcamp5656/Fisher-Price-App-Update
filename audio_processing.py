"""
audio_processing.py
Handles real-time audio effects (Compression/Limiting) using Numba for high performance.
"""

import numpy as np
import math
from numba import jit

@jit(nopython=True, cache=True)
def process_chunk(samples, envelope, gain, threshold, ratio, makeup_gain, limiter_threshold, alpha_attack, alpha_release):
    """
    Numba-optimized function to process audio samples.
    Input `samples` must be float32 or float64.
    """
    n_samples = len(samples)
    output = np.zeros_like(samples)
    
    # Local state variables
    current_env = envelope
    current_gain = gain
    
    # Pre-calculate linear limiter threshold
    # limiter_threshold is in dB, convert to linear amplitude
    limit_thresh_lin = 10.0 ** (limiter_threshold / 20.0)
    
    # Ratio calculation helper (standard compressor math)
    # Gain reduction slope: 1 - (1/ratio)
    slope = 1.0 - (1.0 / ratio)

    for i in range(n_samples):
        sample = samples[i]
        abs_sample = abs(sample)
        
        # --- Envelope Follower (Level Detection) ---
        if abs_sample > current_env:
            current_env = alpha_attack * current_env + (1.0 - alpha_attack) * abs_sample
        else:
            current_env = alpha_release * current_env + (1.0 - alpha_release) * abs_sample
            
        # Protect against log(0)
        if current_env < 1e-9:
            env_db = -120.0
        else:
            env_db = 20.0 * math.log10(current_env)
            
        # --- Compressor Logic ---
        gain_reduction_db = 0.0
        if env_db > threshold:
            gain_reduction_db = (threshold - env_db) * slope
            
        # Total gain in dB (Make-up + Reduction)
        total_gain_db = makeup_gain + gain_reduction_db
        
        # Convert dB gain to linear
        target_gain = 10.0 ** (total_gain_db / 20.0)
        
        # Apply Gain
        compressed_val = sample * target_gain
        
        # --- Limiter Logic (Hard Clip) ---
        # If signal exceeds ceiling, clamp it
        if compressed_val > limit_thresh_lin:
            output[i] = limit_thresh_lin
        elif compressed_val < -limit_thresh_lin:
            output[i] = -limit_thresh_lin
        else:
            output[i] = compressed_val
            
        current_gain = target_gain

    return output, current_env, current_gain

class AudioProcessor:
    def __init__(self, samplerate=44100.0):
        self.samplerate = float(samplerate)
        
        # --- Compressor Settings ---
        self.threshold = -20.0      # dB
        self.ratio = 4.0            # Ratio 4:1
        self.makeup_gain = 4.0      # dB
        self.limiter_threshold = -0.5 # dB (Ceiling)
        
        # Time constants (seconds)
        self.attack_time = 0.010    # 10ms
        self.release_time = 0.100   # 100ms
        
        # Internal State
        self.envelope = 0.0
        self.gain = 1.0
        
        # Coefficients
        self._update_coeffs()

    def _update_coeffs(self):
        # Calculate standard one-pole filter coefficients
        self.alpha_attack = np.exp(-1.0 / (self.attack_time * self.samplerate))
        self.alpha_release = np.exp(-1.0 / (self.release_time * self.samplerate))

    def process(self, int16_samples):
        """
        Process a chunk of int16 audio data.
        1. Converts int16 -> float32
        2. Runs Numba DSP
        3. Converts float32 -> int16
        """
        if len(int16_samples) == 0:
            return int16_samples

        # 1. Convert to Float (-1.0 to 1.0)
        # We use 32768.0 to normalize signed 16-bit integer audio
        samples_float = int16_samples.astype(np.float32) / 32768.0
        
        # 2. Run DSP
        processed_float, self.envelope, self.gain = process_chunk(
            samples_float,
            self.envelope,
            self.gain,
            self.threshold,
            self.ratio,
            self.makeup_gain,
            self.limiter_threshold,
            self.alpha_attack,
            self.alpha_release
        )
        
        # 3. Convert back to Int16
        # Clip to ensure we don't wrap around (which causes hideous digital noise)
        np.clip(processed_float, -1.0, 1.0, out=processed_float)
        
        # Scale back up and cast
        return (processed_float * 32767.0).astype(np.int16)