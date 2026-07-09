import { PageHeader } from "../components/PageHeader";
import { ChatPanel } from "../features/chat/ChatPanel";
import styles from "./Ask.module.css";

export default function Ask() {
  return (
    <>
      <PageHeader
        eyebrow="Research assistant"
        title="Ask ResearchSense"
        description="A preview of the retrieval assistant. Ask in plain English and it points you to relevant researchers and areas. Full RAG answers arrive in a later phase."
      />
      <div className={`container ${styles.body}`}>
        <ChatPanel />
      </div>
    </>
  );
}
