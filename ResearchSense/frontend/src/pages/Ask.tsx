import { PageHeader } from "../components/PageHeader";
import { ChatPanel } from "../features/chat/ChatPanel";
import styles from "./Ask.module.css";

export default function Ask() {
  return (
    <>
      <PageHeader
        eyebrow="Research assistant"
        title="Ask ResearchSense"
        description="Ask in plain English about researchers, publications, projects, or the papers in our library. Answers come only from indexed ResearchSense data; anything outside it is declined."
      />
      <div className={`container ${styles.body}`}>
        <ChatPanel />
      </div>
    </>
  );
}
