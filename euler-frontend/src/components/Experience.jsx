import { CameraControls } from "@react-three/drei";
import { useEffect, useRef } from "react";
import { Avatar } from "./Avatar";

export const Experience = () => {
  const controls = useRef();

  useEffect(() => {
    controls.current.setLookAt(1, 2.2, 10, 0, 1.5, 0);
    controls.current.setLookAt(0.1, 1.7, 1, 0, 1.5, 0, true);
  }, []);

  return (
    <>
      <CameraControls ref={controls} />
      <directionalLight position={[1, 0.5, -3]} intensity={2} color="blue" />
      <directionalLight position={[-1, 0.5, -2]} intensity={2} color="red" />
      <directionalLight position={[1, 1, 3]} intensity={2} />
      <Avatar />
    </>
  );
};
