import { Lipsync } from "wawa-lipsync";
import { ChatWidget } from "./components/ChatWidget";

export const lipsyncManager = new Lipsync({});

function App() {
  return <ChatWidget />;
}

export default App;