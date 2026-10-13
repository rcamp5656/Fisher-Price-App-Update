import React, { useEffect, useState } from "react";
import { Volume2, VolumeX, Bell } from "lucide-react";
import { audioState, audioSampleRate, getVolume, setVolume, testTone, watchAudio, audioEngine } from "../hooks/useMusicBox";

// Speaker status + volume + test chime so "no sound" is diagnosable in one glance
export default function SoundCheck({ compact = false }) {
  const [state, setState] = useState(audioState());
  const [vol, setVol] = useState(getVolume());
  useEffect(() => watchAudio(() => { setState(audioState()); setVol(getVolume()); }), []);
  const blocked = state === "suspended";
  const muted = vol === 0;
  const label = muted ? "MUTED" : blocked ? "SOUND BLOCKED — click to allow" : state === "running" ? `SOUND ON · ${Math.round(audioSampleRate() / 1000)} kHz` : "SOUND READY";
  const chime = () => { audioEngine(); testTone(); };
  return (
    <div data-testid="sound-check" className={`flex items-center gap-2 font-mono text-[11px] ${compact ? "" : "border-2 border-[#1D3557] rounded-lg px-2 py-1 bg-white"}`}>
      <button
        type="button" data-testid="sound-test-button" onClick={chime} title="Play a three-note test chime"
        className={`flex items-center gap-1 font-sans font-black text-[11px] px-2 py-1 rounded border-2 border-[#1D3557] ${blocked || muted ? "bg-[#E63946] text-white" : "bg-[#2A9D8F] text-white"}`}
      >
        {muted ? <VolumeX className="h-3.5 w-3.5" /> : <Bell className="h-3.5 w-3.5" />} TEST
      </button>
      <span data-testid="sound-state" className={`font-bold ${blocked || muted ? "text-[#E63946]" : "text-[#1D3557]"}`}>{label}</span>
      <label className="flex items-center gap-1 ml-1" title="Preview volume">
        <Volume2 className="h-3.5 w-3.5" />
        <input
          type="range" min="0" max="1" step="0.05" value={vol} data-testid="volume-slider"
          onChange={(e) => { const v = Number(e.target.value); setVol(v); setVolume(v); }}
          className="w-20 accent-[#E63946]"
        />
        <span data-testid="volume-value" className="w-8 text-right">{Math.round(vol * 100)}%</span>
      </label>
    </div>
  );
}
