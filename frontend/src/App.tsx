import DemoApp from "./DemoApp";
import RemoteApp from "./RemoteApp";

// `npm run dev:demo` -> sample data. Default mode -> Keycloak login + FastAPI.
export default function App() {
  return import.meta.env.MODE === "demo" ? <DemoApp /> : <RemoteApp />;
}
