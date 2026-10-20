/*
  Avatar robot estilo widget (basado en public/images/robot.svg)
  Procedimental para imitar cabeza redondeada, antenas, parpadeo y bobbing.
  Mantiene integración con lipsyncManager (wawa-lipsync).
*/
import { useFrame } from "@react-three/fiber";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { VISEMES } from "wawa-lipsync";
import { lipsyncManager } from "../App";

export function Avatar(props) {
  const group = useRef();
  const headRef = useRef();
  const antennaLeftRef = useRef();
  const antennaRightRef = useRef();
  const eyeLeftRef = useRef();
  const eyeRightRef = useRef();
  const mouthRef = useRef();
  const leftCheekRef = useRef();
  const rightCheekRef = useRef();

  const [blink, setBlink] = useState(false);
  const [bobTime, setBobTime] = useState(0);

  // Parpadeo aleatorio
  useEffect(() => {
    let blinkTimeout;
    const nextBlink = () => {
      blinkTimeout = setTimeout(() => {
        setBlink(true);
        setTimeout(() => {
          setBlink(false);
          nextBlink();
        }, 160);
      }, THREE.MathUtils.randInt(2000, 4500));
    };
    nextBlink();
    return () => clearTimeout(blinkTimeout);
  }, []);

  useFrame((state, delta) => {
    setBobTime((t) => t + delta);

    if (group.current) {
      // Bob + ligero balanceo como el SVG
      const t = bobTime;
      group.current.position.y = Math.sin(t * 3.5) * 0.04 + Math.sin(t * 1.8) * 0.015;
      group.current.rotation.x = Math.sin(t * 2.2) * 0.01;
      group.current.rotation.y = Math.sin(t * 1.4) * 0.012;
      group.current.rotation.z = Math.sin(t * 1.9) * 0.008;
    }

    if (headRef.current) {
      headRef.current.rotation.x = Math.sin(bobTime * 2.0) * 0.015;
      headRef.current.rotation.y = Math.sin(bobTime * 1.6) * 0.02;
    }

    // Parpadeo
    const blinkScale = blink ? 0.08 : 1;
    if (eyeLeftRef.current) {
      eyeLeftRef.current.scale.y = THREE.MathUtils.lerp(
        eyeLeftRef.current.scale.y,
        blinkScale,
        0.6
      );
    }
    if (eyeRightRef.current) {
      eyeRightRef.current.scale.y = THREE.MathUtils.lerp(
        eyeRightRef.current.scale.y,
        blinkScale,
        0.6
      );
    }

    // Antenas pulsantes
    const pulse = Math.sin(bobTime * 4.2) * 0.25 + 0.75;
    if (antennaLeftRef.current) {
      const s = 1 + pulse * 0.25;
      antennaLeftRef.current.scale.setScalar(
        THREE.MathUtils.lerp(antennaLeftRef.current.scale.x, s, 0.3)
      );
    }
    if (antennaRightRef.current) {
      const s = 1 + pulse * 0.25;
      antennaRightRef.current.scale.setScalar(
        THREE.MathUtils.lerp(antennaRightRef.current.scale.x, s, 0.3)
      );
    }

    // Mejillas sutiles
    const cheekPulse = Math.sin(bobTime * 2.8) * 0.15 + 0.7;
    if (leftCheekRef.current) {
      leftCheekRef.current.scale.setScalar(
        THREE.MathUtils.lerp(leftCheekRef.current.scale.x, cheekPulse, 0.2)
      );
    }
    if (rightCheekRef.current) {
      rightCheekRef.current.scale.setScalar(
        THREE.MathUtils.lerp(rightCheekRef.current.scale.x, cheekPulse, 0.2)
      );
    }

    // Lipsync - boca
    if (mouthRef.current) {
      const viseme = lipsyncManager.viseme;
      const state = lipsyncManager.state;
      let open = 0;
      if (viseme && viseme !== "sil") {
        open = state === "vowel" ? 0.35 : 0.22;
        if (viseme === "aa" || viseme === "E" || viseme === "O") {
          open = 0.45;
        }
      }
      mouthRef.current.scale.y = THREE.MathUtils.lerp(
        mouthRef.current.scale.y,
        0.4 + open,
        state === "vowel" ? 0.25 : 0.35
      );
      mouthRef.current.scale.x = THREE.MathUtils.lerp(
        mouthRef.current.scale.x,
        1.0 + open * 0.3,
        0.25
      );
    }
  });

  return (
    <group {...props} ref={group} dispose={null}>
      {/* Cuello fino */}
      <mesh position={[0, 0.95, 0]}>
        <cylinderGeometry args={[0.08, 0.12, 0.25, 16]} />
        <meshStandardMaterial color="#c7d2fe" metalness={0.1} roughness={0.4} />
      </mesh>

      {/* Cabeza */}
      <group ref={headRef} position={[0, 1.25, 0]}>
        {/* Base */}
        <mesh>
          <boxGeometry args={[0.58, 0.48, 0.48]} />
          <meshStandardMaterial color="#ffffff" metalness={0.05} roughness={0.3} />
        </mesh>
        {/* Redondeado */}
        <mesh position={[0.26, 0, 0]}>
          <sphereGeometry args={[0.24, 20, 20]} />
          <meshStandardMaterial color="#ffffff" metalness={0.05} roughness={0.3} />
        </mesh>
        <mesh position={[-0.26, 0, 0]}>
          <sphereGeometry args={[0.24, 20, 20]} />
          <meshStandardMaterial color="#ffffff" metalness={0.05} roughness={0.3} />
        </mesh>
        <mesh position={[0, 0.22, 0]}>
          <sphereGeometry args={[0.24, 20, 20]} />
          <meshStandardMaterial color="#ffffff" metalness={0.05} roughness={0.3} />
        </mesh>
        <mesh position={[0, -0.22, 0]}>
          <sphereGeometry args={[0.24, 20, 20]} />
          <meshStandardMaterial color="#ffffff" metalness={0.05} roughness={0.3} />
        </mesh>
        <mesh position={[0, 0, 0.22]}>
          <sphereGeometry args={[0.24, 20, 20]} />
          <meshStandardMaterial color="#ffffff" metalness={0.05} roughness={0.3} />
        </mesh>
        <mesh position={[0, 0, -0.22]}>
          <sphereGeometry args={[0.24, 20, 20]} />
          <meshStandardMaterial color="#ffffff" metalness={0.05} roughness={0.3} />
        </mesh>

        {/* Antenas */}
        <group position={[-0.16, 0.38, 0]} rotation={[0, 0, 0.25]}>
          <mesh position={[0, 0.08, 0]}>
            <cylinderGeometry args={[0.012, 0.015, 0.16, 12]} />
            <meshStandardMaterial color="#e0e7ff" metalness={0.2} roughness={0.4} />
          </mesh>
          <mesh ref={antennaLeftRef} position={[0, 0.17, 0]}>
            <sphereGeometry args={[0.028, 16, 16]} />
            <meshStandardMaterial
              color="#fbbf24"
              emissive="#f59e0b"
              emissiveIntensity={0.6}
            />
          </mesh>
        </group>
        <group position={[0.16, 0.38, 0]} rotation={[0, 0, -0.25]}>
          <mesh position={[0, 0.08, 0]}>
            <cylinderGeometry args={[0.012, 0.015, 0.16, 12]} />
            <meshStandardMaterial color="#e0e7ff" metalness={0.2} roughness={0.4} />
          </mesh>
          <mesh ref={antennaRightRef} position={[0, 0.17, 0]}>
            <sphereGeometry args={[0.028, 16, 16]} />
            <meshStandardMaterial
              color="#fbbf24"
              emissive="#f59e0b"
              emissiveIntensity={0.6}
            />
          </mesh>
        </group>

        {/* Orejas */}
        <mesh position={[-0.36, 0, 0]}>
          <boxGeometry args={[0.05, 0.18, 0.14]} />
          <meshStandardMaterial color="#e0e7ff" metalness={0.1} roughness={0.4} />
        </mesh>
        <mesh position={[0.36, 0, 0]}>
          <boxGeometry args={[0.05, 0.18, 0.14]} />
          <meshStandardMaterial color="#e0e7ff" metalness={0.1} roughness={0.4} />
        </mesh>

        {/* Ojos */}
        <group position={[0, -0.02, 0.24]}>
          <mesh ref={eyeLeftRef} position={[-0.1, 0, 0]}>
            <sphereGeometry args={[0.038, 16, 16]} />
            <meshStandardMaterial color="#1e293b" />
          </mesh>
          <mesh position={[-0.095, 0.012, 0.028]}>
            <sphereGeometry args={[0.012, 12, 12]} />
            <meshStandardMaterial color="#ffffff" />
          </mesh>
          <mesh ref={eyeRightRef} position={[0.1, 0, 0]}>
            <sphereGeometry args={[0.038, 16, 16]} />
            <meshStandardMaterial color="#1e293b" />
          </mesh>
          <mesh position={[0.095, 0.012, 0.028]}>
            <sphereGeometry args={[0.012, 12, 12]} />
            <meshStandardMaterial color="#ffffff" />
          </mesh>
        </group>

        {/* Mejillas */}
        <mesh ref={leftCheekRef} position={[-0.16, -0.08, 0.23]}>
          <sphereGeometry args={[0.024, 14, 14]} />
          <meshStandardMaterial color="#fb7185" transparent opacity={0.7} />
        </mesh>
        <mesh ref={rightCheekRef} position={[0.16, -0.08, 0.23]}>
          <sphereGeometry args={[0.024, 14, 14]} />
          <meshStandardMaterial color="#fb7185" transparent opacity={0.7} />
        </mesh>

        {/* Boca */}
        <mesh ref={mouthRef} position={[0, -0.14, 0.24]} scale={[1, 0.4, 1]}>
          <torusGeometry args={[0.07, 0.012, 12, 16, Math.PI]} />
          <meshStandardMaterial color="#1e293b" />
        </mesh>
      </group>
    </group>
  );
}
