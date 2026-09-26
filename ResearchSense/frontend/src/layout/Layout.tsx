import { Suspense } from "react";
import { Outlet } from "react-router-dom";

import Header from "./Header";
import Footer from "./Footer";
import { ChatWidget } from "../features/chat/ChatWidget";
import { useScrollTop } from "../hooks/useScrollTop";
import { Loader } from "../components/StateViews";
import styles from "./Layout.module.css";

export default function Layout() {
  useScrollTop();
  return (
    <div className={styles.shell}>
      {/* First Tab stop: keyboard users skip the header's links. */}
      <a className={styles.skip} href="#main">
        Skip to content
      </a>
      <Header />
      <main id="main" tabIndex={-1} className={styles.main}>
        <Suspense fallback={<Loader />}>
          <Outlet />
        </Suspense>
      </main>
      <Footer />
      {/* Draggable, dockable assistant available on every page. */}
      <ChatWidget />
    </div>
  );
}
