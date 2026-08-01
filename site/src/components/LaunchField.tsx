"use client";

/**
 * The signature element.
 *
 * 462 bars, one per launch auction actually recorded on Robinhood Chain by
 * the GAVEL watcher. Height and colour come from what happened to that
 * launch, not from taste. The camera starts down inside the field, where it
 * looks like a crowd, and scroll lifts it out until the grid resolves and you
 * can see how few of them ever became a pool.
 *
 * The argument is the visual: from inside, every launch looks alike.
 */

import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import launches from "@/app/launches.json";

type Row = { b: number; s: "pool" | "failed" | "live" | "silent"; c: number; lp: number };

const DATA = launches as Row[];

const COLS = 33;
const GAP = 1.28;
const BAR_W = 0.44;

/* Every bar is a launch, so every bar stands at a comparable height —
   letting the successful ones tower would misrepresent the record by making
   97 read as the majority. Colour carries the outcome; the grey crowd is
   supposed to dominate, because it does. */
const TONE: Record<Row["s"], string> = {
  silent: "#464b52", // never became a pool — the bulk
  pool: "#b98d2b", // brass: migrated, liquidity exists
  failed: "#b3372f",
  live: "#e8e4da", // still inside its auction window
};

const HEIGHT: Record<Row["s"], number> = {
  silent: 1.5,
  pool: 2.1,
  failed: 1.7,
  live: 1.8,
};

function Field({ progress }: { progress: React.RefObject<number> }) {
  const mesh = useRef<THREE.InstancedMesh>(null);
  const { camera } = useThree();

  const { matrices, colors, rows } = useMemo(() => {
    const dummy = new THREE.Object3D();
    const matrices: THREE.Matrix4[] = [];
    const colors = new Float32Array(DATA.length * 3);
    const c = new THREE.Color();
    const rows = Math.ceil(DATA.length / COLS);

    DATA.forEach((d, i) => {
      const col = i % COLS;
      const row = Math.floor(i / COLS);
      const h = HEIGHT[d.s] * (0.85 + Math.min(d.lp, 1) * 0.5);
      dummy.position.set(
        (col - COLS / 2) * GAP,
        h / 2,
        (row - rows / 2) * GAP
      );
      dummy.scale.set(BAR_W, h, BAR_W);
      dummy.updateMatrix();
      matrices.push(dummy.matrix.clone());
      c.set(TONE[d.s]);
      c.toArray(colors, i * 3);
    });
    return { matrices, colors, rows };
  }, []);

  useEffect(() => {
    if (!mesh.current) return;
    matrices.forEach((m, i) => mesh.current!.setMatrixAt(i, m));
    mesh.current.instanceMatrix.needsUpdate = true;
  }, [matrices]);

  useFrame((state, delta) => {
    const p = progress.current ?? 0;
    // Inside the crowd -> lifted out above the record.
    const targetY = 1.1 + p * 26;
    const targetZ = 21 - p * 4;
    const targetLookY = p * 1.2;
    camera.position.y += (targetY - camera.position.y) * Math.min(1, delta * 3);
    camera.position.z += (targetZ - camera.position.z) * Math.min(1, delta * 3);
    camera.position.x = Math.sin(state.clock.elapsedTime * 0.08) * 1.6 * (1 - p * 0.7);
    camera.lookAt(0, targetLookY, 0);
  });

  return (
    <instancedMesh
      ref={mesh}
      args={[undefined, undefined, DATA.length]}
      castShadow={false}
    >
      <boxGeometry args={[1, 1, 1]}>
        <instancedBufferAttribute
          attach="attributes-color"
          args={[colors, 3]}
        />
      </boxGeometry>
      <meshStandardMaterial
        vertexColors
        roughness={0.55}
        metalness={0.35}
        toneMapped={false}
      />
    </instancedMesh>
  );
}

function StaticFallback() {
  return (
    <div className="absolute inset-0 grid place-items-center">
      <div className="flex items-end gap-[3px]" aria-hidden>
        {DATA.slice(0, 120).map((d, i) => (
          <span
            key={i}
            style={{
              background: TONE[d.s],
              width: 3,
              height: 8 + HEIGHT[d.s] * 22,
              display: "block",
            }}
          />
        ))}
      </div>
    </div>
  );
}

export default function LaunchField({
  children,
}: {
  children?: React.ReactNode;
}) {
  const progress = useRef(0);
  const host = useRef<HTMLDivElement>(null);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const onChange = () => setReduced(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  useEffect(() => {
    const onScroll = () => {
      const el = host.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const span = rect.height - window.innerHeight;
      progress.current = span > 0 ? Math.min(1, Math.max(0, -rect.top / span)) : 0;
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);

  return (
    <div ref={host} data-hero className="relative h-[230vh]">
      <div className="sticky top-0 h-screen overflow-hidden bg-slate">
        {reduced ? (
          <StaticFallback />
        ) : (
          <Canvas
            dpr={[1, 1.75]}
            camera={{ position: [0, 1.1, 21], fov: 42 }}
            gl={{ antialias: true }}
          >
            <color attach="background" args={["#0e1113"]} />
            <fog attach="fog" args={["#0e1113", 20, 62]} />
            <ambientLight intensity={0.55} />
            <directionalLight position={[6, 14, 8]} intensity={1.5} />
            <directionalLight position={[-8, 4, -6]} intensity={0.4} color="#b98d2b" />
            <Field progress={progress} />
          </Canvas>
        )}
        {children}
      </div>
    </div>
  );
}
