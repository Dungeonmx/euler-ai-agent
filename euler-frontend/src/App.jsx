import { useState } from "react";
import { Loader } from "@react-three/drei";
import { Lipsync } from "wawa-lipsync";
import { UI } from "./components/UI";

export const lipsyncManager = new Lipsync({});

function App() {
  const [audioUrl, setAudioUrl] = useState(null);

  const handleAudioUrl = (url) => {
    setAudioUrl(url);
  };

  return (
    <>
      <Loader />
      <UI audioUrl={audioUrl} onAudioUrl={handleAudioUrl} />
    </>
  );
}

export default App;
