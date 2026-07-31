import "@testing-library/jest-dom/vitest";

// Recharts' <ResponsiveContainer> measures its element via ResizeObserver +
// getBoundingClientRect to decide the chart's pixel size. jsdom does no
// layout, so both normally report zero, and chart children (bars, lines,
// legend) never render. Stub both so containers report a fixed, positive
// size and charts render their content in tests.
class ResizeObserverStub {
  observe(): void {}
  unobserve(): void {}
  disconnect(): void {}
}
// @ts-expect-error -- jsdom has no ResizeObserver implementation
globalThis.ResizeObserver ??= ResizeObserverStub;

Object.defineProperty(HTMLElement.prototype, "getBoundingClientRect", {
  configurable: true,
  value: () => ({
    width: 800,
    height: 600,
    top: 0,
    left: 0,
    bottom: 600,
    right: 800,
    x: 0,
    y: 0,
    toJSON() {},
  }),
});
