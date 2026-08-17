import { Loader } from "@react-three/drei";
import { Lipsync } from "wawa-lipsync";
import { UI } from "./components/UI";

export const lipsyncManager = new Lipsync({});

function App() {
  return (
    <>
      <Loader />
      <UI />
    </>
  );
}

export default App;
