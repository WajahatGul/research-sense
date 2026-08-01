import { Outlet } from "react-router-dom";

import Header from "./Header";
import Footer from "./Footer";
import { ChatWidget } from "../features/chat/ChatWidget";
import { useScrollTop } from "../hooks/useScrollTop";
import styles from "./Layout.module.css";

export default function Layout() {
  useScrollTop();
  return (
    <div className={styles.shell}>
      <Header />
      <main className={styles.main}>
        <Outlet />
      </main>
      <Footer />
      {/* Draggable, dockable assistant available on every page. */}
      <ChatWidget />
    </div>
  );
}
