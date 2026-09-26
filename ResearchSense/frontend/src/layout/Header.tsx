import { useEffect, useState } from "react";
import { NavLink, Link } from "react-router-dom";

import { Wordmark } from "../components/Wordmark";
import { SESSION_EVENT } from "../lib/session";
import styles from "./Header.module.css";

// The places people come for, in the order they usually need them. Nine
// equal links (Guide, Projects and Library included) made every item compete
// and pushed the bar into a hamburger on ordinary laptops; the rest now live
// in the footer, and the guide is offered to newcomers on the home page.
const NAV = [
  { to: "/researchers", label: "Researchers" },
  { to: "/publications", label: "Publications" },
  { to: "/topics", label: "Research Areas" },
  { to: "/collaboration", label: "Collaboration" },
  { to: "/analytics", label: "Analytics" },
];

function hasSession(): boolean {
  try {
    return Boolean(localStorage.getItem("rs_token"));
  } catch {
    return false;
  }
}

export default function Header() {
  const [open, setOpen] = useState(false);
  const [signedIn, setSignedIn] = useState(hasSession);

  useEffect(() => {
    const sync = () => setSignedIn(hasSession());
    window.addEventListener(SESSION_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(SESSION_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  const close = () => setOpen(false);
  const linkClass = ({ isActive }: { isActive: boolean }) =>
    isActive ? `${styles.link} ${styles.active}` : styles.link;

  return (
    <header className={styles.header}>
      <div className={`container ${styles.bar}`}>
        <Link to="/" className={styles.brand} onClick={close}>
          <Wordmark />
        </Link>

        <button
          className={styles.toggle}
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          aria-controls="site-nav"
          onClick={() => setOpen((v) => !v)}
        >
          <span />
          <span />
          <span />
        </button>

        <nav
          id="site-nav"
          aria-label="Main"
          className={`${styles.nav} ${open ? styles.navOpen : ""}`}
        >
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} className={linkClass} onClick={close}>
              {item.label}
            </NavLink>
          ))}
          <span className={styles.divider} aria-hidden="true" />
          <NavLink to="/search" className={linkClass} onClick={close}>
            <svg viewBox="0 0 24 24" className={styles.icon} aria-hidden="true">
              <circle cx="11" cy="11" r="7" />
              <path d="m20 20-3.5-3.5" />
            </svg>
            Search
          </NavLink>
          <Link to="/portal" className={styles.cta} onClick={close}>
            {signedIn ? "Your portal" : "Sign in"}
          </Link>
        </nav>
      </div>
    </header>
  );
}
