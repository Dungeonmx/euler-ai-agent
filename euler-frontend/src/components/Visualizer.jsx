import { Chat } from "./Chat";

export const Visualizer = ({ audioUrl, onAudioUrl }) => {
  return (
    <div className="flex flex-col gap-4">
      <Chat audioUrl={audioUrl} onAudioUrl={onAudioUrl} />
    </div>
  );
};
