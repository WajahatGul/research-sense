import { Outlet } from "react-router-dom";

import Header from "./Header";
import Footer from "./Footer";
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
    </div>
  );
}
