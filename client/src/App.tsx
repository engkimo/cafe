import { Switch, Route } from "wouter";
import Home from "@/pages/Home";

function App() {
  return (
    <Switch>
      <Route path="/" component={Home} />
    </Switch>
  );
}

export default App;
