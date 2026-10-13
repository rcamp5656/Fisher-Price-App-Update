import React, { Suspense, useMemo } from "react";
import { Canvas, useLoader } from "@react-three/fiber";
import { OrbitControls, ContactShadows } from "@react-three/drei";
import { STLLoader } from "three/examples/jsm/loaders/STLLoader.js";

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

export default function RecordViewer({ url }) {
  return (
    <Canvas
      key={url}
      shadows
      camera={{ position: [0, 95, 95], fov: 42, near: 0.5, far: 1000 }}
      dpr={[1, 2]}
      data-testid="record-3d-canvas"
    >
      <color attach="background" args={["#F4F1EA"]} />
      <ambientLight intensity={0.65} />
      <directionalLight position={[50, 90, 40]} intensity={1.15} castShadow />
      <directionalLight position={[-50, 30, -40]} intensity={0.4} />
      <Suspense fallback={<Spinner />}>
        <Disc url={url} />
      </Suspense>
      <ContactShadows position={[0, -2.2, 0]} opacity={0.35} scale={200} blur={2.2} far={40} />
      <OrbitControls enablePan minDistance={12} maxDistance={240} autoRotate autoRotateSpeed={0.8} />
    </Canvas>
  );
}
