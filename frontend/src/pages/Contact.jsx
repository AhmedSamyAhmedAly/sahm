import { Link } from "react-router-dom";

export default function Contact() {
  return (
    <div className="container" style={{ maxWidth: 720 }}>
      <Link to="/" className="link">← Back</Link>
      <h1 style={{ marginTop: 12 }}>Contact us</h1>
      <div className="card" style={{ padding: 20, lineHeight: 1.7 }}>
        <p>
          Questions, account help, or feedback? Reach the Saaed admin team — we're a small group
          and happy to help.
        </p>
        <p style={{ marginBottom: 6 }}><b>Email</b></p>
        <p style={{ marginTop: 0 }}>
          <a href="mailto:ahmed.samy@sahm.app">ahmed.samy@sahm.app</a>
        </p>
        <p style={{ color: "var(--muted)", fontSize: 13 }}>
          For account access (invite code, password reset, or suspension), the admin can help you
          from the admin panel.
        </p>
      </div>
    </div>
  );
}
