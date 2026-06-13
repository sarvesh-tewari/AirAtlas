import { Component, type ReactNode } from "react";

// Isolates a widget: if it throws, show a small inline notice instead of blanking the app.
export class ErrorBoundary extends Component<
  { children: ReactNode; label?: string },
  { failed: boolean }
> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidUpdate(prev: { children: ReactNode }) {
    // Recover when inputs change (e.g. the user switches standard/city).
    if (this.state.failed && prev.children !== this.props.children) {
      this.setState({ failed: false });
    }
  }

  render() {
    if (this.state.failed) {
      return (
        <section className="card p-5 text-sm text-body">
          {this.props.label ?? "This section"} couldn't render for the current selection.
        </section>
      );
    }
    return this.props.children;
  }
}
