import PicksView from "../components/PicksView.jsx";

// The home page: curated BUY suggestions only (sell/hold live on Portfolio).
export default function Dashboard() {
  return <PicksView suggestionsOnly showKpis title="Today's Suggestions" />;
}
