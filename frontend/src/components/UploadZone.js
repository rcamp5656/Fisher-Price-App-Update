import React, { useRef, useState } from "react";
import { UploadCloud, FileMusic } from "lucide-react";

export default function UploadZone({ file, onFile, onError, label, testId }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const pick = (f) => {
    if (!f) return;
    if (!/\.(mid|midi)$/i.test(f.name)) {
      onError("That is not a MIDI file. Please choose a .mid or .midi file.");
      return;
    }
    onError(null);
    onFile(f);
  };

  return (
    <div
      data-testid={testId}
      onClick={() => inputRef.current?.click()}
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); pick(e.dataTransfer.files?.[0]); }}
      className={`cursor-pointer border-4 border-dashed rounded-xl p-4 text-center transition-colors duration-150 ${
        dragging ? "border-[#E63946] bg-[#E63946]/5" : "border-[#457B9D] bg-white"
      }`}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".mid,.midi"
        className="hidden"
        data-testid={`${testId}-input`}
        onChange={(e) => { pick(e.target.files?.[0]); e.target.value = ""; }}
      />
      {label && <p className="font-mono text-[10px] uppercase text-[#457B9D] mb-1">{label}</p>}
      <UploadCloud className="h-7 w-7 mx-auto mb-1 text-[#457B9D]" />
      {file ? (
        <p className="font-mono text-sm font-bold flex items-center justify-center gap-2 break-all">
          <FileMusic className="h-4 w-4 shrink-0" /> {file.name}
        </p>
      ) : (
        <>
          <p className="font-mono text-sm font-bold">Drop a .mid file here</p>
          <p className="font-mono text-xs text-[#457B9D]">or click to browse</p>
        </>
      )}
    </div>
  );
}
