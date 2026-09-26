import { PageHeader } from "../components/PageHeader";
import { ChatPanel } from "../features/chat/ChatPanel";
import styles from "./Ask.module.css";

export default function Ask() {
  return (
    <>
      <PageHeader
        eyebrow="Research assistant"
        title="Ask ResearchSense"
        description="Ask in plain English about researchers, publications or papers. Answers come only from ResearchSense data, with sources; if the data cannot answer, the assistant says so."
      />
      <div className={`container ${styles.body}`}>
        <ChatPanel prefillFromUrl />
      </div>
    </>
  );
}
