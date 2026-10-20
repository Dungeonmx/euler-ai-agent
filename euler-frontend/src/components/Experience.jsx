import { CameraControls } from "@react-three/drei";
import { useEffect, useRef } from "react";
import { Avatar } from "./Avatar";

export const Experience = () => {
  const controls = useRef();

  useEffect(() => {
    controls.current.setLookAt(0.8, 2.0, 8, 0, 1.4, 0);
    controls.current.setLookAt(0.15, 1.9, 1.4, 0, 1.25, 0, true);
  }, []);

  return (
    <>
      <CameraControls ref={controls} />
      <directionalLight position={[1, 0.8, -2]} intensity={2} color="#a5b4fc" />
      <directionalLight position={[-1, 0.6, -1.5]} intensity={2} color="#f9a8d4" />
      <directionalLight position={[0.5, 1.2, 2.5]} intensity={2.2} />
      <Avatar />
    </>
  );
};
