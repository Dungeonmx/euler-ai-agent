import { Canvas } from "@react-three/fiber";
import { Suspense } from "react";
import { Experience } from "./Experience";
import { Visualizer } from "./Visualizer";

export const UI = ({ audioUrl, onAudioUrl }) => {
  return (
    <section className="flex flex-col-reverse lg:flex-row overflow-hidden h-full w-full">
      <div className="p-10 flex-1 overflow-y-auto">
        <Visualizer audioUrl={audioUrl} onAudioUrl={onAudioUrl} />
      </div>
      <div className="flex-1 bg-gradient-to-b from-pink-400 to-pink-200 relative">
        <Canvas shadows camera={{ position: [12, 8, 26], fov: 30 }}>
          <Suspense>
            <Experience audioUrl={audioUrl} />
          </Suspense>
        </Canvas>
      </div>
    </section>
  );
};
