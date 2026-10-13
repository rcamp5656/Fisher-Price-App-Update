import React, { useEffect, useState } from "react";
import { Disc3 } from "lucide-react";

export const CREDITS = {
  author: "Russ Campbell",
  copyright: "Copyright 2026 Russ Campbell. All rights reserved.",
  title: "Fisher-Price Record Maker",
  dedication: "Dedicated To My Fiancée Barbara",
};

// Shown ~2.5 s on every load, then fades into the app; a click/tap skips it
export default function Splash({ duration = 2500 }) {
  const [phase, setPhase] = useState("in");
  useEffect(() => {
    const t1 = setTimeout(() => setPhase("out"), duration);
    const t2 = setTimeout(() => setPhase("gone"), duration + 600);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [duration]);
  if (phase === "gone") return null;
  const skip = () => { setPhase("out"); setTimeout(() => setPhase("gone"), 400); };
  return (
    <div
      data-testid="splash-screen" onClick={skip} role="button" tabIndex={0} onKeyDown={skip}
      className={`fixed inset-0 z-[100] flex items-center justify-center bg-[#1D3557] text-[#F4F1EA] cursor-pointer transition-opacity duration-500 ${phase === "out" ? "opacity-0" : "opacity-100"}`}
    >
      <div className="text-center px-8 select-none">
        <Disc3 className="h-20 w-20 mx-auto mb-6 text-[#E63946] animate-[spin_4s_linear_infinite]" />
        <h1 data-testid="splash-title" className="font-sans font-black text-4xl sm:text-5xl lg:text-6xl tracking-tight">{CREDITS.title}</h1>
        <p data-testid="splash-dedication" className="font-mono text-base md:text-lg mt-4 text-[#E9C46A] italic">{CREDITS.dedication}</p>
        <p data-testid="splash-author" className="font-sans font-black text-lg md:text-xl mt-8">{CREDITS.author}</p>
        <p data-testid="splash-copyright" className="font-mono text-xs md:text-sm mt-2 text-[#A8DADC]">{CREDITS.copyright}</p>
        <p className="font-mono text-[10px] mt-10 text-[#457B9D]">click anywhere to continue</p>
      </div>
    </div>
  );
}
