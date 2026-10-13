import React, { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Canvas, useLoader, useThree } from "@react-three/fiber";
import { OrbitControls, ContactShadows } from "@react-three/drei";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";
import { ScanSearch, Disc3 } from "lucide-react";

function Disc({ url }) {
  const geom = useLoader(STLLoader, url);
  const prepared = useMemo(() => {
    const g = geom.clone();
    g.center();
    g.computeVertexNormals();
    return g;
  }, [geom]);

  return (
    <mesh geometry={prepared} rotation={[-Math.PI / 2, 0, 0]} castShadow receiveShadow>
      <meshStandardMaterial color="#B9A9E3" roughness={0.55} metalness={0.05} flatShading />
    </mesh>
  );
}

function Spinner() {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]}>
      <torusGeometry args={[38, 6, 16, 80]} />
      <meshStandardMaterial color="#457B9D" roughness={0.5} wireframe />
    </mesh>
  );
}

// "label" = straight-down close-up of the centre so the curved title + dedication can be read
const VIEWS = { disc: { pos: [0, 95, 95], target: [0, 0, 0] }, label: { pos: [0, 70, 0.01], target: [0, 0, 0] } };

function CameraRig({ view, controls }) {
  const { camera } = useThree();
  useEffect(() => {
    const v = VIEWS[view];
    camera.position.set(...v.pos);
    camera.lookAt(...v.target);
    if (controls.current) { controls.current.target.set(...v.target); controls.current.update(); }
  }, [view, camera, controls]);
  return null;
}

export default function RecordViewer({ url }) {
  const [view, setView] = useState("disc");
  const controls = useRef(null);
  return (
    <div className="sticky top-4 h-[calc(100vh-220px)] min-h-[480px] w-full">
      <Canvas
        key={url}
        shadows
        camera={{ position: VIEWS.disc.pos, fov: 42, near: 0.5, far: 1000 }}
        dpr={[1, 2]}
        data-testid="record-3d-canvas"
      >
        <color attach="background" args={["#F4F1EA"]} />
        <ambientLight intensity={view === "label" ? 0.45 : 0.65} />
        <directionalLight position={[50, 90, 40]} intensity={1.15} castShadow />
        <directionalLight position={[-50, 30, -40]} intensity={0.4} />
        {view === "label" && <directionalLight position={[60, 12, 20]} intensity={1.6} />}
        <Suspense fallback={<Spinner />}>
          <Disc url={url} />
        </Suspense>
        <ContactShadows position={[0, -2.2, 0]} opacity={0.35} scale={200} blur={2.2} far={40} />
        <OrbitControls ref={controls} enablePan minDistance={12} maxDistance={240} autoRotate={view === "disc"} autoRotateSpeed={0.8} />
        <CameraRig view={view} controls={controls} />
      </Canvas>
      <div className="absolute top-3 right-3 flex rounded-lg border-2 border-[#1D3557] overflow-hidden font-sans font-black text-xs bg-white">
        {[["disc", Disc3, "FULL DISC"], ["label", ScanSearch, "READ LABEL"]].map(([v, Icon, l]) => (
          <button
            key={v} type="button" data-testid={`viewer-${v}`} onClick={() => setView(v)}
            className={`px-3 py-1.5 flex items-center gap-1 ${view === v ? "bg-[#1D3557] text-white" : "hover:bg-[#E9C46A]"}`}
            title={v === "label" ? "Straight-down close-up: title arc, record number and the Barbara dedication ring" : "Rotating view of the whole disc"}
          >
            <Icon className="h-3.5 w-3.5" /> {l}
          </button>
        ))}
      </div>
      {view === "label" && (
        <div data-testid="viewer-label-hint" className="absolute top-12 right-3 font-mono text-[10px] text-[#457B9D] bg-white/80 border border-[#1D3557] rounded px-2 py-1 max-w-[220px]">
          Title arc on the left · record number by the spindle · “Dedicated To My Fiancée Barbara” ring on the right (2.4 mm letters, raised 0.6 mm). Scroll to zoom closer.
        </div>
      )}
    </div>
  );
}
