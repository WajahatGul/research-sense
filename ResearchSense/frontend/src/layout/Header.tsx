import { useState } from "react";
import { NavLink, Link } from "react-router-dom";

import { Wordmark } from "../components/Wordmark";
import styles from "./Header.module.css";

const NAV = [
  { to: "/researchers", label: "Researchers" },
  { to: "/publications", label: "Publications" },
  { to: "/topics", label: "Research Areas" },
  { to: "/projects", label: "Projects" },
  { to: "/collaboration", label: "Collaboration" },
  { to: "/analytics", label: "Analytics" },
  { to: "/library", label: "Library" },
  { to: "/portal", label: "Portal" },
];

export default function Header() {
  const [open, setOpen] = useState(false);

  return (
    <header className={styles.header}>
      <div className={`container ${styles.bar}`}>
        <Link to="/" className={styles.brand} onClick={() => setOpen(false)}>
          <Wordmark />
        </Link>

        <button
          className={styles.toggle}
          aria-label="Toggle navigation"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <span />
          <span />
          <span />
        </button>

        <nav className={`${styles.nav} ${open ? styles.navOpen : ""}`}>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                isActive ? `${styles.link} ${styles.active}` : styles.link
              }
              onClick={() => setOpen(false)}
            >
              {item.label}
            </NavLink>
          ))}
          <Link to="/ask" className={styles.cta} onClick={() => setOpen(false)}>
            Ask ResearchSense
          </Link>
        </nav>
      </div>
    </header>
  );
}
