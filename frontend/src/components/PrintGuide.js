import React, { useEffect, useState } from "react";
import { Printer, ChevronDown, ChevronUp, Layers, Compass, Package, Settings2, Sparkles } from "lucide-react";
import { CARD } from "../lib/fp";

const SECTIONS = [
  {
    icon: Layers, title: "Layer height & nozzle",
    tips: [
      "0.10–0.12 mm layers (pins are only 1.2 mm tall × 1 mm wide — coarse layers round them off).",
      "Standard 0.4 mm nozzle is fine; 0.25 mm gives crisper pin edges.",
      "Slow the outer walls to ~30–40 mm/s so the 1 mm pins don't smear.",
    ],
  },
  {
    icon: Compass, title: "Orientation",
    tips: [
      "Print flat, label side up (side A up). No supports needed — grooves are open-topped.",
      "Two-sided disc: DON'T print the full body — the underside bumps get first-layer squish. Print HALF A and HALF B pins-up (flat backs), then glue back-to-back; use the spindle + 4 drive holes (toothpicks / a 6 mm rod) to align.",
      "Put the Z-seam on 'rear' or 'aligned' so seam blobs don't land on a pin.",
    ],
  },
  {
    icon: Package, title: "Material",
    tips: [
      "PLA or PETG — stiff plastics pluck the tines cleanly. Avoid TPU/flexibles.",
      "Original discs are rigid ABS-like plastic; Fred Murphy found clear resin gave the sharpest notes.",
      "Resin printers: 0.05 mm layers, cure fully — soft pins make dull notes.",
    ],
  },
  {
    icon: Settings2, title: "Slicer settings",
    tips: [
      "100 % scale, Ø121 mm — do not shrink to fit; the spindle and 4 drive pegs must line up.",
      "3–4 perimeters, 40 %+ infill (or 100 % — the disc is thin anyway).",
      "Turn off elephant's-foot compensation if the disc won't drop onto the spindle, or ream the 6.4 mm hole lightly.",
      "Two-sided: 5 mm total (two 2.5 mm halves). Never use supports — nothing on the disc needs them.",
      "Pin bumps below 0.45 mm radius are thinner than a 0.4 mm line: enable Arachne/variable line width, or use a 0.25 mm nozzle or resin.",
    ],
  },
  {
    icon: Sparkles, title: "After printing",
    tips: [
      "Deburr with a fingernail or soft brush — no stringing between pins.",
      "Check every pin survived in the slicer preview before you print (tiny islands sometimes get dropped).",
      "If the tune plays too fast/slow, the spring wind matters: wind fully, then adjust the capture window and re-cut.",
    ],
  },
];

export default function PrintGuide({ defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  useEffect(() => { setOpen(defaultOpen); }, [defaultOpen]);
  return (
    <div data-testid="print-guide" className={`${CARD} col-span-12 overflow-hidden`}>
      <button
        data-testid="print-guide-toggle"
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between p-5 text-left hover:bg-[#F4F1EA] transition-colors duration-150"
      >
        <span className="font-sans font-black text-xl tracking-tight flex items-center gap-2">
          <Printer className="h-5 w-5" /> PRINT GUIDE — clean pins, first try
        </span>
        {open ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
      </button>
      {open && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 px-5 pb-5">
          {SECTIONS.map(({ icon: Icon, title, tips }) => (
            <div key={title} className="border-2 border-[#1D3557] rounded-lg p-4 bg-[#F4F1EA]">
              <h4 className="font-sans font-black text-sm tracking-tight flex items-center gap-2 mb-2">
                <Icon className="h-4 w-4 text-[#E63946]" /> {title.toUpperCase()}
              </h4>
              <ul className="font-mono text-xs text-[#1D3557] space-y-1.5 list-disc pl-4">
                {tips.map((t) => <li key={t}>{t}</li>)}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
